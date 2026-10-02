# identity.py
#
# Copyright 2026 mirkobrombin <brombin94@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import select
import socket
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import parse_qs, quote, urlencode, urlparse

import gi
import requests

gi.require_version("Gio", "2.0")
gi.require_version("Secret", "1")
from gi.repository import Gio, GLib, Secret  # noqa: E402

from bottles.backend.globals import Paths, is_cpak
from bottles.backend.logger import Logger
from bottles.backend.utils.proc import ProcUtils

logging = Logger()

MAGIC = 0x31424953
VERSION = 1
RESPONSE_BIT = 0x8000
MAX_PAYLOAD = 1024 * 1024
MAX_FIELD_COUNT = 64
MAX_CALLBACK_URI = 64 * 1024
MAX_ACTIVATION_TOKEN = 4096

CALLBACK_SCHEME = "ms-appx-web"
CALLBACK_HOST = "microsoft.aad.brokerplugin"
CALLBACK_ACTIVATION_TOKEN = "_bottles_activation_token"
CALLBACK_SIZE = struct.Struct("<I")

HEADER = struct.Struct("<IHHIIi")
FIELD = struct.Struct("<HHI")

OP_PING = 1
OP_AUTHORIZE = 2
OP_GET_TOKEN = 3
OP_CLEAR = 4
OP_LIST_ACCOUNTS = 5

STATUS_OK = 0
STATUS_CANCELED = 1
STATUS_UNAVAILABLE = 2
STATUS_INVALID_REQUEST = 3
STATUS_AUTH_FAILED = 4
STATUS_NOT_FOUND = 5
STATUS_PROTOCOL_ERROR = 6

FIELD_CLIENT_ID = 1
FIELD_SCOPES = 2
FIELD_AUTHORITY = 3
FIELD_LOGIN_HINT = 4
FIELD_CALLER_ID = 5
FIELD_ACCESS_TOKEN = 10
FIELD_ID_TOKEN = 11
FIELD_EXPIRES_AT = 12
FIELD_ACCOUNT_ID = 13
FIELD_USERNAME = 14
FIELD_FIRST_NAME = 15
FIELD_LAST_NAME = 16
FIELD_DISPLAY_NAME = 17
FIELD_TENANT_ID = 18
FIELD_CLIENT_INFO = 19
FIELD_ERROR = 20
FIELD_POLICY = 21
FIELD_ACCOUNTS = 22

MAX_ACCOUNTS = 128
PERSONAL_TENANT = "9188040d-6c67-4c5b-b112-36a304b66dad"

CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9.-]{1,128}$")
STATE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
TENANT_PATTERN = re.compile(
    r"^(common|organizations|consumers|[0-9a-fA-F-]{36})$"
)

CALLER_CLIENT_IDS = {
    "2b379600-b42b-4fe9-a59c-a312fb934935": "d3590ed6-52b3-4102-aeff-aad2292ab01c",
}

SCOPE_ALIASES = {
    "service::https://licensing.m365.svc.cloud.microsoft/::MBI_SSL_SHORT": (
        "https://licensing.m365.svc.cloud.microsoft/.default"
    ),
}

UNSUPPORTED_IDENTITY_RESOURCES = {
    "https://events.data.microsoft.com/OneCollector/1.0/",
}

SECRET_SCHEMA = Secret.Schema.new(
    "com.usebottles.Identity",
    Secret.SchemaFlags.NONE,
    {
        "context": Secret.SchemaAttributeType.STRING,
        "client": Secret.SchemaAttributeType.STRING,
        "account": Secret.SchemaAttributeType.STRING,
    },
)


class ProtocolError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class AuthenticationCanceled(AuthenticationError):
    pass


class AuthenticationStorageError(AuthenticationError):
    pass


def _secret_call(callback, *args):
    try:
        return callback(*args)
    except GLib.Error as exc:
        raise AuthenticationStorageError(
            "Secure credential storage is unavailable. Start or unlock a Secret Service provider, such as GNOME Keyring or KWallet, and try again."
        ) from exc


@dataclass
class Message:
    opcode: int
    request_id: int
    status: int
    fields: dict[int, bytes]


@dataclass
class AuthorizationResult:
    access_token: str
    id_token: str
    refresh_token: str
    expires_at: int
    account_id: str
    username: str
    first_name: str
    last_name: str
    display_name: str
    tenant_id: str
    client_info: str
    scopes: str = ""


@dataclass
class _BridgeProcess:
    socket_path: str
    process: subprocess.Popen


def encode_message(message: Message) -> bytes:
    chunks = []
    for field_id, value in message.fields.items():
        if not isinstance(value, bytes):
            raise TypeError("protocol fields must be bytes")
        chunks.append(FIELD.pack(field_id, 0, len(value)))
        chunks.append(value)
    payload = b"".join(chunks)
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError("payload is too large")
    return HEADER.pack(
        MAGIC,
        VERSION,
        message.opcode,
        message.request_id,
        len(payload),
        message.status,
    ) + payload


def decode_message(data: bytes) -> Message:
    if len(data) < HEADER.size:
        raise ProtocolError("short header")
    magic, version, opcode, request_id, payload_size, status = HEADER.unpack_from(data)
    if magic != MAGIC or version != VERSION:
        raise ProtocolError("unsupported protocol")
    if payload_size > MAX_PAYLOAD or len(data) != HEADER.size + payload_size:
        raise ProtocolError("invalid payload size")

    fields = {}
    offset = HEADER.size
    while offset < len(data):
        if len(fields) == MAX_FIELD_COUNT or offset + FIELD.size > len(data):
            raise ProtocolError("invalid field table")
        field_id, flags, size = FIELD.unpack_from(data, offset)
        offset += FIELD.size
        if flags or size > len(data) - offset or field_id in fields:
            raise ProtocolError("invalid field")
        fields[field_id] = data[offset : offset + size]
        offset += size
    return Message(opcode, request_id, status, fields)


def _recv_exact(connection: socket.socket, size: int) -> bytes:
    chunks = []
    received = 0
    while received < size:
        chunk = connection.recv(size - received)
        if not chunk:
            raise ProtocolError("connection closed")
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


def receive_message(connection: socket.socket) -> Message:
    header = _recv_exact(connection, HEADER.size)
    magic, version, opcode, request_id, payload_size, status = HEADER.unpack(header)
    if magic != MAGIC or version != VERSION or payload_size > MAX_PAYLOAD:
        raise ProtocolError("invalid header")
    payload = _recv_exact(connection, payload_size) if payload_size else b""
    return decode_message(header + payload)


def _text(fields: dict[int, bytes], field_id: int, default: str = "") -> str:
    value = fields.get(field_id)
    if value is None:
        return default
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("invalid UTF-8 field") from exc


def _required_text(fields: dict[int, bytes], field_id: int) -> str:
    value = _text(fields, field_id)
    if not value:
        raise ProtocolError("missing required field")
    return value


def _authority(fields: dict[int, bytes], default: str) -> str:
    value = _text(fields, FIELD_AUTHORITY, default).lower()
    if len(value) > 128 or any(ord(character) < 33 or ord(character) > 126 for character in value):
        raise ProtocolError("invalid authority")
    if value.startswith("https://"):
        parsed = urlparse(value)
        if (
            parsed.netloc not in (
                "login.microsoftonline.com", "login.windows.net", "login.microsoft.com"
            )
            or parsed.params or parsed.query or parsed.fragment
        ):
            raise ProtocolError("invalid authority")
        tenant = parsed.path.removeprefix("/").removesuffix("/")
        canonical = f"https://{parsed.netloc}/{tenant}"
        if value not in (canonical, canonical + "/"):
            raise ProtocolError("invalid authority")
        value = tenant
    if not TENANT_PATTERN.fullmatch(value):
        raise ProtocolError("invalid authority")
    return value


def _field(value: str) -> bytes:
    return value.encode("utf-8")


def _resolve_client_id(fields: dict[int, bytes]) -> str:
    client_id = _text(fields, FIELD_CLIENT_ID)
    caller_id = _text(fields, FIELD_CALLER_ID).lower()
    if bool(client_id) == bool(caller_id):
        raise ProtocolError("exactly one identity field is required")
    if client_id:
        return client_id
    if not CLIENT_ID_PATTERN.fullmatch(caller_id):
        raise ProtocolError("invalid caller ID")
    try:
        return CALLER_CLIENT_IDS[caller_id]
    except KeyError as exc:
        raise ProtocolError("unsupported caller ID") from exc


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_claims(token: str) -> dict:
    if not isinstance(token, str):
        raise AuthenticationError("invalid ID token")
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError, json.JSONDecodeError) as exc:
        raise AuthenticationError("invalid ID token") from exc
    if not isinstance(claims, dict):
        raise AuthenticationError("invalid ID token")
    return claims


def _validate_text(value: str, name: str, maximum: int) -> None:
    if (
        len(value) > maximum
        or not value.isascii()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ProtocolError(f"invalid {name}")


class SecretTokenStore:
    def __init__(self, context: str):
        self.context = context

    def _cpak_request(self, operation, attributes, value=""):
        try:
            response = subprocess.run(
                ["cpak-secrets"],
                input=json.dumps({
                    "operation": operation,
                    "attributes": attributes,
                    "value": value,
                }),
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=130, check=True,
            )
            if len(response.stdout) > 12 * 1024 * 1024:
                raise ValueError("oversized credential response")
            result = json.loads(response.stdout)
            if not isinstance(result, dict) or not isinstance(result.get("changed"), bool):
                raise ValueError("invalid credential response")
            entries = result.get("entries")
            if not isinstance(entries, list) or len(entries) > MAX_ACCOUNTS:
                raise ValueError("invalid credential entries")
            if operation == "get" and len(entries) > 1:
                raise ValueError("ambiguous credential lookup")
            for entry in entries:
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("attributes"), dict)
                    or not isinstance(entry.get("value"), str)
                    or len(entry["value"].encode("utf-8")) > 64 * 1024
                    or any(entry["attributes"].get(key) != expected
                           for key, expected in attributes.items())
                ):
                    raise ValueError("credential scope mismatch")
            return result
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            reason = exc.__class__.__name__
            broker_error = (getattr(exc, "stderr", "") or "").strip()
            if broker_error in (
                "secure credential storage is unavailable or locked",
                "secret operation is not permitted",
            ):
                reason = broker_error
            logging.warning(f"cpak credential broker failed: {reason}")
            raise AuthenticationStorageError(
                "Secure credential storage is unavailable. Start or unlock a Secret Service provider, such as GNOME Keyring or KWallet, and try again."
            ) from exc

    def _write(self, attributes, label, value):
        if is_cpak():
            return self._cpak_request("put", attributes, value)["changed"]
        return _secret_call(
            Secret.password_store_sync, SECRET_SCHEMA, attributes,
            Secret.COLLECTION_DEFAULT, label, value, None,
        )

    def _read(self, attributes):
        if is_cpak():
            entries = self._cpak_request("get", attributes)["entries"]
            return entries[0]["value"] if entries else None
        return _secret_call(Secret.password_lookup_sync, SECRET_SCHEMA, attributes, None)

    def _delete(self, attributes):
        if is_cpak():
            return self._cpak_request("delete", attributes)["changed"]
        return _secret_call(Secret.password_clear_sync, SECRET_SCHEMA, attributes, None)

    def _entries(self, attributes):
        if is_cpak():
            for entry in self._cpak_request("search", attributes)["entries"]:
                yield entry["attributes"], entry["value"]
            return
        items = _secret_call(
            Secret.password_search_sync, SECRET_SCHEMA, attributes,
            Secret.SearchFlags.ALL | Secret.SearchFlags.UNLOCK, None,
        )
        for item in items:
            secret = _secret_call(item.retrieve_secret_sync, None)
            if secret is None:
                raise AuthenticationStorageError("credential store entry is locked")
            yield item.get_attributes(), secret.get_text()

    def _attributes(self, client_id: str, account_id: str) -> dict[str, str]:
        attributes = {
            "context": self.context,
            "client": client_id,
        }
        if account_id:
            attributes["account"] = account_id
        return attributes

    def store(self, client_id: str, result: AuthorizationResult) -> None:
        value = json.dumps(
            {
                "refresh_token": result.refresh_token,
                "id_token": result.id_token,
                "account_id": result.account_id,
                "username": result.username,
                "first_name": result.first_name,
                "last_name": result.last_name,
                "display_name": result.display_name,
                "tenant_id": result.tenant_id,
                "client_info": result.client_info,
            },
            separators=(",", ":"),
        )
        if not self._write(
            self._attributes(client_id, result.account_id),
            "Bottles Microsoft identity",
            value,
        ):
            raise AuthenticationError("the credential store rejected the token")
        if not self._write(
            self._attributes(client_id, "__current__"),
            "Bottles Microsoft identity account",
            json.dumps({"account_id": result.account_id}, separators=(",", ":")),
        ):
            raise AuthenticationError("the credential store rejected the account")

    def load(self, client_id: str, account_id: str) -> Optional[dict]:
        if not account_id:
            current = self._read(self._attributes(client_id, "__current__"))
            if not current:
                return None
            try:
                account_id = json.loads(current)["account_id"]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise AuthenticationError("invalid credential store account") from exc
        value = self._read(self._attributes(client_id, account_id))
        if not value:
            return None
        try:
            result = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AuthenticationError("invalid credential store entry") from exc
        if not isinstance(result, dict) or not result.get("refresh_token"):
            raise AuthenticationError("incomplete credential store entry")
        return result

    def accounts(self, client_id: str, authority: str) -> list[tuple[str, str]]:
        attributes = {"context": self.context}
        if client_id:
            attributes["client"] = client_id
        accounts = {}
        for item_attributes, raw_value in self._entries(attributes):
            if any(item_attributes.get(key) != value for key, value in attributes.items()):
                raise AuthenticationStorageError("credential store scope mismatch")
            account_id = item_attributes.get("account", "")
            if not account_id or account_id == "__current__":
                continue
            try:
                value = json.loads(raw_value)
            except (json.JSONDecodeError, TypeError) as exc:
                raise AuthenticationStorageError("invalid credential store entry") from exc
            if (
                not isinstance(value, dict)
                or value.get("account_id") != account_id
                or not isinstance(value.get("refresh_token"), str)
                or not value["refresh_token"]
                or not isinstance(value.get("username"), str)
                or not isinstance(value.get("tenant_id"), str)
            ):
                raise AuthenticationStorageError("incomplete credential store entry")
            tenant = value["tenant_id"].lower()
            if authority == "consumers" and tenant != PERSONAL_TENANT:
                continue
            if authority == "organizations" and (not tenant or tenant == PERSONAL_TENANT):
                continue
            if authority not in {"common", "consumers", "organizations"} and tenant != authority:
                continue
            accounts[account_id] = value["username"]
            if len(accounts) > MAX_ACCOUNTS:
                raise AuthenticationStorageError("too many stored accounts")
        return sorted(accounts.items())

    def clear(self, client_id: str, account_id: str) -> bool:
        if not account_id:
            current = self._read(self._attributes(client_id, "__current__"))
            if not current:
                return False
            try:
                account_id = json.loads(current)["account_id"]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise AuthenticationError("invalid credential store account") from exc
        cleared = self._delete(self._attributes(client_id, account_id))
        self._delete(self._attributes(client_id, "__current__"))
        return cleared


def _callback_socket_path(state: str) -> str:
    name = hashlib.sha256(state.encode("ascii")).hexdigest()[:32]
    return os.path.join(Paths.temp, "identity-callbacks", f"{name}.sock")


def _callback_socket_address(path: str) -> tuple[int, str]:
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory, flags)
    os.fchmod(descriptor, 0o700)
    return descriptor, f"/proc/self/fd/{descriptor}/{os.path.basename(path)}"


def _parse_callback_uri(uri: str) -> tuple[str, dict[str, list[str]]]:
    parsed = urlparse(uri)
    if (
        parsed.scheme.lower() != CALLBACK_SCHEME
        or parsed.netloc.lower() != CALLBACK_HOST
        or parsed.fragment
    ):
        raise ProtocolError("invalid identity callback")
    try:
        query = parse_qs(parsed.query, max_num_fields=16)
    except ValueError as exc:
        raise ProtocolError("invalid identity callback query") from exc
    states = query.get("state", [])
    if len(states) != 1 or not STATE_PATTERN.fullmatch(states[0]):
        raise ProtocolError("invalid identity callback state")
    codes = query.get("code", [])
    errors = query.get("error", [])
    if len(codes) > 1 or len(errors) > 1 or bool(codes) == bool(errors):
        raise ProtocolError("invalid identity callback result")
    return states[0], query


def forward_identity_callback(uri: str, activation_token: str = "") -> bool:
    try:
        state, query = _parse_callback_uri(uri)
        if CALLBACK_ACTIVATION_TOKEN in query:
            return False
        if activation_token:
            _validate_text(
                activation_token,
                "activation token",
                MAX_ACTIVATION_TOKEN,
            )
            uri += (
                f"&{CALLBACK_ACTIVATION_TOKEN}="
                f"{quote(activation_token, safe='')}"
            )
        payload = uri.encode("utf-8")
        if len(payload) > MAX_CALLBACK_URI:
            return False
        descriptor, address = _callback_socket_address(
            _callback_socket_path(state)
        )
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(2)
                connection.connect(address)
                connection.sendall(CALLBACK_SIZE.pack(len(payload)) + payload)
                return _recv_exact(connection, 1) == b"\x01"
        finally:
            os.close(descriptor)
    except (OSError, ProtocolError, UnicodeError):
        return False


class RedirectListener:
    def __init__(
        self,
        state: str,
        client_id: str,
        cancel_event: Optional[threading.Event] = None,
        activation_callback: Optional[Callable[[str], None]] = None,
    ):
        self.state = state
        self.client_id = client_id.lower()
        self.cancel_event = cancel_event
        self.activation_callback = activation_callback
        self.disconnect_event = None
        self.result = None
        self.socket_path = _callback_socket_path(state)
        self.socket_directory, socket_address = _callback_socket_address(
            self.socket_path
        )
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.server.bind(socket_address)
            os.chmod(self.socket_path, 0o600)
            self.server.listen(1)
            self.server.settimeout(1)
        except OSError:
            self.close()
            raise

    @property
    def redirect_uri(self) -> str:
        return f"{CALLBACK_SCHEME}://{CALLBACK_HOST}/{self.client_id}"

    def wait(self, timeout: int = 600) -> dict:
        deadline = time.monotonic() + timeout
        try:
            while self.result is None and time.monotonic() < deadline:
                if (self.cancel_event and self.cancel_event.is_set()) or (
                    self.disconnect_event and self.disconnect_event.is_set()
                ):
                    raise AuthenticationCanceled("authentication canceled")
                try:
                    connection, _ = self.server.accept()
                except TimeoutError:
                    continue
                with connection:
                    connection.settimeout(2)
                    try:
                        size = CALLBACK_SIZE.unpack(
                            _recv_exact(connection, CALLBACK_SIZE.size)
                        )[0]
                        if not size or size > MAX_CALLBACK_URI:
                            raise ProtocolError("invalid identity callback size")
                        uri = _recv_exact(connection, size).decode("utf-8")
                        self.result = self._callback_result(uri)
                        connection.sendall(b"\x01")
                    except (OSError, ProtocolError, UnicodeError):
                        try:
                            connection.sendall(b"\x00")
                        except OSError:
                            pass
        finally:
            self.close()
        if self.result is None:
            raise AuthenticationError("authentication timed out")
        return self.result

    def _callback_result(self, uri: str) -> dict:
        state, query = _parse_callback_uri(uri)
        parsed = urlparse(uri)
        if (
            state != self.state
            or parsed.path.lstrip("/").lower() != self.client_id
        ):
            raise ProtocolError("identity callback does not match")
        activation_tokens = query.get(CALLBACK_ACTIVATION_TOKEN, [])
        if len(activation_tokens) > 1:
            raise ProtocolError("invalid identity activation token")
        if activation_tokens:
            activation_token = activation_tokens[0]
            _validate_text(
                activation_token,
                "activation token",
                MAX_ACTIVATION_TOKEN,
            )
            if self.activation_callback:
                self.activation_callback(activation_token)
        return {
            "code": query.get("code", [None])[0],
            "error": query.get("error", [None])[0],
            "error_description": query.get("error_description", [None])[0],
        }

    def close(self) -> None:
        if self.server:
            self.server.close()
            self.server = None
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
        if self.socket_directory is not None:
            os.close(self.socket_directory)
            self.socket_directory = None


class MicrosoftIdentityProvider:
    def __init__(
        self,
        store,
        session: Optional[requests.Session] = None,
        open_uri: Optional[Callable[[str], None]] = None,
        listener_factory=RedirectListener,
        auth_complete: Optional[Callable[[Optional[bool], str], None]] = None,
    ):
        self.store = store
        self.session = session or requests.Session()
        self.open_uri = open_uri or self._open_uri
        self.listener_factory = listener_factory
        self.auth_complete = auth_complete
        self.cancel_event = None
        self.cache = {}

    @staticmethod
    def _open_uri(uri: str) -> None:
        if not Gio.AppInfo.launch_default_for_uri(uri, None):
            raise AuthenticationError("unable to open the system browser")

    @staticmethod
    def _validate_request(
        client_id: str, authority: str, scopes: str, login_hint: str = ""
    ) -> None:
        if not CLIENT_ID_PATTERN.fullmatch(client_id):
            raise ProtocolError("invalid client ID")
        if not TENANT_PATTERN.fullmatch(authority):
            raise ProtocolError("invalid authority")
        scope_items = scopes.split()
        if not scope_items or len(scope_items) > 32 or len(scopes) > 4096:
            raise ProtocolError("invalid scope")
        if any(
            not item.isascii()
            or len(item) > 512
            or any(ord(character) < 33 or ord(character) == 127 for character in item)
            for item in scope_items
        ):
            raise ProtocolError("invalid scope")
        _validate_text(login_hint, "login hint", 320)

    @staticmethod
    def _normalize_scopes(scopes: str) -> str:
        if scopes in UNSUPPORTED_IDENTITY_RESOURCES:
            raise AuthenticationError("unsupported identity resource")
        scopes = SCOPE_ALIASES.get(scopes, scopes)
        requested = scopes.split()
        defaults = ["openid", "profile", "email", "offline_access"]
        return " ".join(defaults + [item for item in requested if item not in defaults])

    def authorize(
        self, client_id: str, authority: str, scopes: str, login_hint: str
    ) -> AuthorizationResult:
        scopes = self._normalize_scopes(scopes)
        self._validate_request(client_id, authority, scopes, login_hint)
        try:
            return self.get_token(client_id, authority, scopes, "", login_hint)
        except AuthenticationStorageError as exc:
            if self.auth_complete:
                self.auth_complete(False, str(exc))
            raise
        except AuthenticationError:
            pass
        verifier = _base64url(secrets.token_bytes(64))
        challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
        state = _base64url(secrets.token_bytes(32))
        nonce = _base64url(secrets.token_bytes(32))
        try:
            listener = self.listener_factory(state, client_id)
            listener.disconnect_event = self.cancel_event
        except OSError as exc:
            error = AuthenticationError("unable to prepare the sign-in callback")
            if self.auth_complete:
                self.auth_complete(False, str(error))
            raise error from exc
        parameters = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": listener.redirect_uri,
            "response_mode": "query",
            "scope": scopes,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "nonce": nonce,
            "client_info": "1",
        }
        if login_hint:
            parameters["login_hint"] = login_hint
        endpoint = (
            f"https://login.microsoftonline.com/{authority}/oauth2/v2.0/authorize"
        )
        try:
            if self.cancel_event and self.cancel_event.is_set():
                raise AuthenticationCanceled("authentication canceled")
            try:
                self.open_uri(f"{endpoint}?{urlencode(parameters)}")
            except (GLib.Error, OSError) as exc:
                raise AuthenticationError("unable to open the system browser") from exc
            response = listener.wait()
            if self.cancel_event and self.cancel_event.is_set():
                raise AuthenticationCanceled("authentication canceled")
            if response.get("error"):
                raise AuthenticationError(
                    response.get("error_description") or response["error"]
                )
            code = response.get("code")
            if not code:
                raise AuthenticationError("authorization returned no code")
            token = self._request_token(
                authority,
                {
                    "client_id": client_id,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": listener.redirect_uri,
                    "code_verifier": verifier,
                    "scope": scopes,
                },
            )
            result = self._result_from_token(token, client_id, nonce)
            if self.cancel_event and self.cancel_event.is_set():
                raise AuthenticationCanceled("authentication canceled")
            self.store.store(client_id, result)
            self.cache[(client_id, authority, scopes, result.account_id)] = result
        except AuthenticationError as exc:
            if self.auth_complete:
                self.auth_complete(None if isinstance(exc, AuthenticationCanceled) else False, str(exc))
            raise
        finally:
            close = getattr(listener, "close", None)
            if close:
                close()
        if self.auth_complete:
            self.auth_complete(True, "")
        return result

    def get_token(
        self,
        client_id: str,
        authority: str,
        scopes: str,
        account_id: str,
        login_hint: str = "",
    ) -> AuthorizationResult:
        scopes = self._normalize_scopes(scopes)
        self._validate_request(client_id, authority, scopes, login_hint)
        stored = self.store.load(client_id, account_id)
        if self.cancel_event and self.cancel_event.is_set():
            raise AuthenticationCanceled("authentication canceled")
        if not stored:
            raise AuthenticationError("account not found")
        if login_hint and login_hint.casefold() != stored.get("username", "").casefold():
            raise AuthenticationError("a different account was requested")
        account_id = stored.get("account_id") or account_id
        cached = self.cache.get((client_id, authority, scopes, account_id))
        if cached and cached.expires_at > int(time.time()) + 300:
            return cached
        token = self._request_token(
            authority,
            {
                "client_id": client_id,
                "grant_type": "refresh_token",
                "refresh_token": stored["refresh_token"],
                "scope": scopes,
            },
        )
        if "refresh_token" not in token:
            token["refresh_token"] = stored["refresh_token"]
        if "id_token" not in token:
            token["id_token"] = stored.get("id_token", "")
        result = self._result_from_token(token, client_id)
        if self.cancel_event and self.cancel_event.is_set():
            raise AuthenticationCanceled("authentication canceled")
        self.store.store(client_id, result)
        self.cache[(client_id, authority, scopes, result.account_id)] = result
        return result

    def _request_token(self, authority: str, data: dict) -> dict:
        endpoint = f"https://login.microsoftonline.com/{authority}/oauth2/v2.0/token"
        try:
            response = self.session.post(
                endpoint, data={**data, "client_info": "1"}, timeout=(10, 60), allow_redirects=False
            )
            value = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AuthenticationError("token endpoint failed") from exc
        if response.status_code != 200 or not isinstance(value, dict):
            message = (
                value.get("error_description") if isinstance(value, dict) else None
            )
            raise AuthenticationError(message or "token endpoint rejected the request")
        return value

    @staticmethod
    def _result_from_token(
        token: dict, client_id: str, expected_nonce: Optional[str] = None
    ) -> AuthorizationResult:
        access_token = token.get("access_token", "")
        id_token = token.get("id_token", "")
        refresh_token = token.get("refresh_token", "")
        if (
            not isinstance(access_token, str)
            or not isinstance(id_token, str)
            or not isinstance(refresh_token, str)
            or not access_token
            or not refresh_token
            or not id_token
        ):
            raise AuthenticationError("incomplete token response")
        claims = _decode_claims(id_token)
        audience = claims.get("aud")
        if audience != client_id:
            raise AuthenticationError("unexpected ID token audience")
        if expected_nonce and claims.get("nonce") != expected_nonce:
            raise AuthenticationError("unexpected ID token nonce")
        now = int(time.time())
        try:
            expires_at = now + max(0, int(token.get("expires_in", 0)))
        except (TypeError, ValueError) as exc:
            raise AuthenticationError("invalid token lifetime") from exc
        if expires_at <= now:
            raise AuthenticationError("invalid token lifetime")
        account_id = claims.get("oid") or claims.get("sub") or ""
        username = claims.get("preferred_username") or claims.get("email") or ""
        if not account_id or not username:
            raise AuthenticationError("incomplete account identity")
        first_name = claims.get("given_name", "")
        last_name = claims.get("family_name", "")
        display_name = claims.get("name") or username
        tenant_id = claims.get("tid", "")
        client_info = token.get("client_info", "")
        scopes = token.get("scope", "")
        values = (
            account_id,
            username,
            first_name,
            last_name,
            display_name,
            tenant_id,
            client_info,
            scopes,
        )
        if any(not isinstance(value, str) for value in values):
            raise AuthenticationError("invalid account identity")
        return AuthorizationResult(
            access_token,
            id_token,
            refresh_token,
            expires_at,
            account_id,
            username,
            first_name,
            last_name,
            display_name,
            tenant_id,
            client_info,
            scopes,
        )


def result_fields(result: AuthorizationResult) -> dict[int, bytes]:
    return {
        FIELD_SCOPES: _field(result.scopes),
        FIELD_ACCESS_TOKEN: _field(result.access_token),
        FIELD_ID_TOKEN: _field(result.id_token),
        FIELD_EXPIRES_AT: _field(str(result.expires_at)),
        FIELD_ACCOUNT_ID: _field(result.account_id),
        FIELD_USERNAME: _field(result.username),
        FIELD_FIRST_NAME: _field(result.first_name),
        FIELD_LAST_NAME: _field(result.last_name),
        FIELD_DISPLAY_NAME: _field(result.display_name),
        FIELD_TENANT_ID: _field(result.tenant_id),
        FIELD_CLIENT_INFO: _field(result.client_info),
    }


class IdentityBridgeServer:
    def __init__(self, socket_path: str, context: str, provider=None):
        self.socket_path = socket_path
        self.provider = provider or MicrosoftIdentityProvider(SecretTokenStore(context))
        self.last_activity = time.monotonic()

    def dispatch(self, request: Message) -> Message:
        fields = request.fields
        try:
            if request.status or request.opcode & RESPONSE_BIT:
                raise ProtocolError("invalid request header")
            if request.opcode == OP_PING:
                if fields:
                    raise ProtocolError("unexpected field")
                return Message(
                    OP_PING | RESPONSE_BIT, request.request_id, STATUS_OK, {}
                )
            allowed_fields = {
                OP_AUTHORIZE: {
                    FIELD_CLIENT_ID,
                    FIELD_CALLER_ID,
                    FIELD_SCOPES,
                    FIELD_AUTHORITY,
                    FIELD_LOGIN_HINT,
                    FIELD_POLICY,
                },
                OP_GET_TOKEN: {
                    FIELD_CLIENT_ID,
                    FIELD_SCOPES,
                    FIELD_AUTHORITY,
                    FIELD_ACCOUNT_ID,
                },
                OP_CLEAR: {FIELD_CLIENT_ID, FIELD_ACCOUNT_ID},
                OP_LIST_ACCOUNTS: {FIELD_CLIENT_ID, FIELD_AUTHORITY},
            }.get(request.opcode)
            if allowed_fields is None:
                raise ProtocolError("unsupported operation")
            if set(fields) - allowed_fields:
                raise ProtocolError("unexpected field")
            if request.opcode == OP_LIST_ACCOUNTS:
                client_id = _text(fields, FIELD_CLIENT_ID)
                if client_id and not CLIENT_ID_PATTERN.fullmatch(client_id):
                    raise ProtocolError("invalid client ID")
                client_id = CALLER_CLIENT_IDS.get(client_id.lower(), client_id)
                authority = _authority(fields, "common")
                accounts = self.provider.store.accounts(client_id, authority)
                if len(accounts) > MAX_ACCOUNTS:
                    raise AuthenticationStorageError("too many stored accounts")
                payload = bytearray(struct.pack("<I", len(accounts)))
                for account in accounts:
                    for value in account:
                        encoded = value.encode("utf-8")
                        if not encoded or len(encoded) > 4096 or "\x00" in value:
                            raise AuthenticationStorageError("invalid stored account")
                        payload.extend(struct.pack("<I", len(encoded)))
                        payload.extend(encoded)
                        if len(payload) > MAX_PAYLOAD:
                            raise AuthenticationStorageError("stored account list is too large")
                return Message(
                    request.opcode | RESPONSE_BIT, request.request_id,
                    STATUS_OK, {FIELD_ACCOUNTS: bytes(payload)},
                )
            client_id = (
                _resolve_client_id(fields)
                if request.opcode == OP_AUTHORIZE
                else _required_text(fields, FIELD_CLIENT_ID)
            )
            account_id = _text(fields, FIELD_ACCOUNT_ID)
            _validate_text(account_id, "account ID", 256)
            if request.opcode == OP_AUTHORIZE:
                scopes = _required_text(fields, FIELD_SCOPES)
                _validate_text(_text(fields, FIELD_POLICY), "policy", 256)
                result = self.provider.authorize(
                    client_id,
                    _authority(fields, "organizations"),
                    scopes,
                    _text(fields, FIELD_LOGIN_HINT),
                )
                return Message(
                    request.opcode | RESPONSE_BIT,
                    request.request_id,
                    STATUS_OK,
                    result_fields(result),
                )
            if request.opcode == OP_GET_TOKEN:
                result = self.provider.get_token(
                    client_id,
                    _authority(fields, "organizations"),
                    _required_text(fields, FIELD_SCOPES),
                    account_id,
                )
                return Message(
                    request.opcode | RESPONSE_BIT,
                    request.request_id,
                    STATUS_OK,
                    result_fields(result),
                )
            if request.opcode == OP_CLEAR:
                cleared = self.provider.store.clear(client_id, account_id)
                status = STATUS_OK if cleared else STATUS_NOT_FOUND
                return Message(
                    request.opcode | RESPONSE_BIT, request.request_id, status, {}
                )
            raise ProtocolError("unsupported operation")
        except ProtocolError as exc:
            return Message(
                request.opcode | RESPONSE_BIT,
                request.request_id,
                STATUS_INVALID_REQUEST,
                {FIELD_ERROR: _field(str(exc))},
            )
        except AuthenticationCanceled as exc:
            return Message(
                request.opcode | RESPONSE_BIT,
                request.request_id,
                STATUS_CANCELED,
                {FIELD_ERROR: _field(str(exc))},
            )
        except AuthenticationError as exc:
            return Message(
                request.opcode | RESPONSE_BIT,
                request.request_id,
                STATUS_AUTH_FAILED,
                {FIELD_ERROR: _field(str(exc))},
            )

    def _handle_connection(self, connection: socket.socket) -> None:
        request = receive_message(connection)
        canceled = threading.Event()
        finished = threading.Event()

        def watch_disconnect():
            while not finished.wait(0.1):
                try:
                    ready, _, _ = select.select([connection], [], [], 0)
                    if ready:
                        canceled.set()
                        return
                except (OSError, ValueError):
                    canceled.set()
                    return

        watcher = threading.Thread(target=watch_disconnect, daemon=True)
        self.provider.cancel_event = canceled
        watcher.start()
        try:
            response = self.dispatch(request)
            if not canceled.is_set():
                connection.sendall(encode_message(response))
        finally:
            finished.set()
            watcher.join()
            self.provider.cancel_event = None

    def _has_clients(self) -> bool:
        marker = f"SODA_IDENTITY_BRIDGE_SOCKET={self.socket_path}"
        for process in ProcUtils.get_procs():
            if int(process.pid) == os.getpid():
                continue
            try:
                if marker in process.get_env().split("\x00"):
                    return True
            except UnicodeError:
                continue
        return False

    def serve(self, idle_timeout: int = 600) -> None:
        os.makedirs(os.path.dirname(self.socket_path), mode=0o700, exist_ok=True)
        os.chmod(os.path.dirname(self.socket_path), 0o700)
        old_umask = os.umask(0o077)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        bound = False
        try:
            listener.bind(self.socket_path)
            bound = True
            listener.listen(4)
            listener.settimeout(1)
            while True:
                if time.monotonic() - self.last_activity >= idle_timeout:
                    if not self._has_clients():
                        break
                    self.last_activity = time.monotonic()
                try:
                    connection, _ = listener.accept()
                except TimeoutError:
                    continue
                with connection:
                    if hasattr(socket, "SO_PEERCRED"):
                        credentials = connection.getsockopt(
                            socket.SOL_SOCKET, socket.SO_PEERCRED, 12
                        )
                        _pid, uid, _gid = struct.unpack("3i", credentials)
                        if uid != os.getuid():
                            continue
                    connection.settimeout(620)
                    try:
                        self._handle_connection(connection)
                    except (OSError, ProtocolError):
                        continue
                    self.last_activity = time.monotonic()
        finally:
            listener.close()
            os.umask(old_umask)
            if bound:
                try:
                    os.unlink(self.socket_path)
                except FileNotFoundError:
                    pass


_bridges = {}
_bridges_lock = threading.Lock()


def _reap_bridge(context: str, bridge: _BridgeProcess) -> None:
    bridge.process.wait()
    with _bridges_lock:
        if _bridges.get(context) is bridge:
            del _bridges[context]


def _bridge_ready(socket_path: str) -> bool:
    request_id = secrets.randbits(32)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.2)
            connection.connect(socket_path)
            connection.sendall(encode_message(Message(OP_PING, request_id, 0, {})))
            response = receive_message(connection)
    except (OSError, ProtocolError):
        return False
    return (
        response.opcode == OP_PING | RESPONSE_BIT
        and response.request_id == request_id
        and response.status == STATUS_OK
        and not response.fields
    )


def start_identity_bridge(context: str) -> Optional[str]:
    with _bridges_lock:
        bridge = _bridges.get(context)
        if bridge:
            if bridge.process.poll() is None:
                return bridge.socket_path
            del _bridges[context]
        base = os.environ.get("XDG_RUNTIME_DIR") or Paths.temp
        directory = os.path.join(base, "bottles-identity")
        os.makedirs(directory, mode=0o700, exist_ok=True)
        socket_path = os.path.join(directory, f"{secrets.token_hex(16)}.sock")
        module = "bottles.backend.identity"
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
            module = "bottles.backend.identity_ui"
        command = [
            sys.executable,
            "-m",
            module,
            "--serve",
            "--socket",
            socket_path,
            "--context",
            hashlib.sha256(context.encode("utf-8")).hexdigest(),
        ]
        env = os.environ.copy()
        package_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (package_path, env.get("PYTHONPATH")))
        )
        try:
            process = subprocess.Popen(
                command,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
        except OSError:
            logging.warning("Unable to start the Soda identity bridge")
            return None
        bridge = _BridgeProcess(socket_path, process)
        threading.Thread(
            target=_reap_bridge, args=(context, bridge), daemon=True
        ).start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if _bridge_ready(socket_path):
                if process.poll() is not None:
                    break
                _bridges[context] = bridge
                return socket_path
            time.sleep(0.02)
        try:
            process.terminate()
        except OSError:
            pass
        logging.warning("The Soda identity bridge did not create its socket")
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--socket")
    parser.add_argument("--context")
    args = parser.parse_args()
    if not args.serve or not args.socket or not args.context:
        parser.error("--serve, --socket and --context are required")
    IdentityBridgeServer(args.socket, args.context).serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
