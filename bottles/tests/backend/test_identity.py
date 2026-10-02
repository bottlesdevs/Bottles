import base64
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

import pytest

from bottles.backend.identity import (
    FIELD_ACCESS_TOKEN,
    FIELD_ACCOUNT_ID,
    FIELD_ACCOUNTS,
    FIELD_AUTHORITY,
    FIELD_CALLER_ID,
    FIELD_CLIENT_ID,
    FIELD_ERROR,
    FIELD_ID_TOKEN,
    FIELD_CLIENT_INFO,
    FIELD_EXPIRES_AT,
    FIELD_LOGIN_HINT,
    FIELD_POLICY,
    FIELD_SCOPES,
    MAGIC,
    OP_AUTHORIZE,
    OP_GET_TOKEN,
    OP_LIST_ACCOUNTS,
    OP_PING,
    RESPONSE_BIT,
    STATUS_INVALID_REQUEST,
    STATUS_OK,
    AuthenticationCanceled,
    AuthenticationError,
    AuthenticationStorageError,
    AuthorizationResult,
    IdentityBridgeServer,
    Message,
    MicrosoftIdentityProvider,
    ProtocolError,
    RedirectListener,
    SecretTokenStore,
    GLib,
    _BridgeProcess,
    _bridges,
    _bridge_ready,
    decode_message,
    encode_message,
    forward_identity_callback,
    receive_message,
    start_identity_bridge,
    _authority,
    result_fields,
)


@pytest.mark.parametrize("value,expected", (
    (b"common", "common"),
    (b"https://login.microsoftonline.com/organizations/", "organizations"),
    (b"https://login.windows.net/consumers", "consumers"),
    (b"HTTPS://LOGIN.MICROSOFT.COM/common/", "common"),
    (b"https://login.microsoftonline.com/00000000-0000-0000-0000-000000000001/", "00000000-0000-0000-0000-000000000001"),
))
def test_authority_accepts_microsoft_issuer_uri(value, expected):
    assert _authority({FIELD_AUTHORITY: value}, "common") == expected


@pytest.mark.parametrize("value", (
    b"http://login.microsoftonline.com/common",
    b"https://evil.example/common",
    b"https://login.microsoftonline.com.evil.example/common",
    b"https://user@login.microsoftonline.com/common",
    b"https://login.microsoftonline.com:443/common",
    b"https://login.microsoftonline.com/common?tenant=consumers",
    b"https://login.microsoftonline.com/common#fragment",
    b"https://login.microsoftonline.com/common/extra",
    b"https://login.microsoftonline.com//common",
    b"https://login.microsoftonline.com/%63ommon",
    b"https://login.microsoftonline.com/common?",
    b"https://login.microsoftonline.com/common#",
    b"https://login.micro\nsoftonline.com/common",
    b"https://login.microsoftonline.com/com\tmon",
))
def test_authority_rejects_untrusted_or_ambiguous_uri(value):
    with pytest.raises(ProtocolError, match="invalid authority"):
        _authority({FIELD_AUTHORITY: value}, "common")


def _id_token(client_id, nonce="nonce", username="user@example.com"):
    header = base64.urlsafe_b64encode(b"{}").rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "aud": client_id,
                "nonce": nonce,
                "oid": "account-id",
                "preferred_username": username,
                "given_name": "Test",
                "family_name": "User",
                "name": "Test User",
                "tid": "tenant-id",
            }
        ).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.signature"


class Store:
    def __init__(self):
        self.values = {}

    def store(self, client_id, result):
        self.values[(client_id, result.account_id)] = {
            "refresh_token": result.refresh_token,
            "id_token": result.id_token,
        }

    def load(self, client_id, account_id):
        return self.values.get((client_id, account_id))

    def clear(self, client_id, account_id):
        return self.values.pop((client_id, account_id), None) is not None


class Response:
    status_code = 200

    def __init__(self, value):
        self.value = value

    def json(self):
        return self.value


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, data, timeout, allow_redirects):
        self.requests.append((url, data, timeout, allow_redirects))
        return Response(self.responses.pop(0))


class Listener:
    def __init__(self, state, client_id):
        self.state = state
        self.redirect_uri = (
            "ms-appx-web://microsoft.aad.brokerplugin/" + client_id
        )

    def wait(self):
        return {"code": "authorization-code", "error": None}

    def close(self):
        pass


def test_bridge_disconnect_cancels_authorization(tmp_path):
    entered = threading.Event()
    canceled = threading.Event()

    class Provider:
        cancel_event = None

        def authorize(self, *_args):
            entered.set()
            if self.cancel_event.wait(2):
                canceled.set()
                raise AuthenticationCanceled("authentication canceled")
            raise AssertionError("disconnect was not delivered")

    server = IdentityBridgeServer(str(tmp_path / "bridge.sock"), "test", Provider())
    client, connection = socket.socketpair()
    worker = threading.Thread(target=server._handle_connection, args=(connection,))
    worker.start()
    try:
        client.sendall(encode_message(Message(OP_AUTHORIZE, 1, 0, {
            FIELD_CLIENT_ID: b"client", FIELD_AUTHORITY: b"common", FIELD_SCOPES: b"openid"
        })))
        assert entered.wait(1)
        client.close()
        assert canceled.wait(1)
        worker.join(1)
        assert not worker.is_alive()
        assert server.provider.cancel_event is None
    finally:
        client.close()
        connection.close()
        worker.join(3)


def test_cancellation_during_token_response_does_not_store_or_cache():
    canceled = threading.Event()
    completed = []
    store = Store()
    opened = []

    class TokenSession:
        def post(self, _url, data, **_kwargs):
            canceled.set()
            return Response({
                "access_token": "access", "refresh_token": "refresh", "expires_in": 3600,
                "id_token": _id_token("client", parse_qs(urlparse(opened[0]).query)["nonce"][0]),
            })

    provider = MicrosoftIdentityProvider(
        store, TokenSession(), opened.append, Listener,
        lambda success, message: completed.append((success, message)),
    )
    provider.cancel_event = canceled
    with pytest.raises(AuthenticationCanceled):
        provider.authorize("client", "common", "openid", "")
    assert store.values == {}
    assert provider.cache == {}
    assert completed == [(None, "authentication canceled")]


def test_unavailable_keyring_reports_error_without_opening_browser(monkeypatch):
    opened = []
    completed = []

    def fail_lookup(*_args):
        raise GLib.Error("internal bus path must not reach the UI")

    monkeypatch.setattr("bottles.backend.identity.Secret.password_lookup_sync", fail_lookup)
    provider = MicrosoftIdentityProvider(
        SecretTokenStore("isolated"), open_uri=opened.append,
        auth_complete=lambda success, message: completed.append((success, message)),
    )
    with pytest.raises(AuthenticationStorageError):
        provider.authorize("client", "common", "openid", "")
    assert opened == []
    assert completed == [(
        False,
        "Secure credential storage is unavailable. Start or unlock a Secret Service provider, such as GNOME Keyring or KWallet, and try again.",
    )]


def test_protocol_round_trip():
    request = Message(
        OP_AUTHORIZE,
        7,
        0,
        {
            FIELD_CLIENT_ID: b"client",
            FIELD_SCOPES: b"openid profile",
        },
    )
    assert decode_message(encode_message(request)) == request


def test_failed_bind_preserves_running_bridge():
    socket_path = os.path.join(
        os.environ["TMPDIR"], f"bridge-{time.time_ns()}.sock"
    )
    server = IdentityBridgeServer(socket_path, "test", Store())
    worker = threading.Thread(target=server.serve, kwargs={"idle_timeout": 2})
    worker.start()
    try:
        deadline = time.monotonic() + 1
        while not _bridge_ready(socket_path) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert _bridge_ready(socket_path)
        with pytest.raises(OSError):
            IdentityBridgeServer(socket_path, "test", Store()).serve()
        assert os.path.exists(socket_path)
        assert _bridge_ready(socket_path)
    finally:
        server.last_activity = 0
        worker.join(3)
    assert not worker.is_alive()
    assert not os.path.exists(socket_path)


def test_failed_bind_preserves_existing_file(tmp_path):
    socket_path = tmp_path / "bridge.sock"
    socket_path.write_text("existing file")
    with pytest.raises(OSError):
        IdentityBridgeServer(str(socket_path), "test", Store()).serve()
    assert socket_path.read_text() == "existing file"


def test_bridge_stays_available_while_client_is_alive():
    socket_path = os.path.join(
        os.environ["TMPDIR"], f"bridge-{time.time_ns()}.sock"
    )
    env = os.environ.copy()
    env["SODA_IDENTITY_BRIDGE_SOCKET"] = socket_path
    client = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"], env=env)
    server = IdentityBridgeServer(socket_path, "test", Store())
    worker = threading.Thread(target=server.serve, kwargs={"idle_timeout": 1})
    worker.start()
    try:
        deadline = time.monotonic() + 1
        while not _bridge_ready(socket_path) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert _bridge_ready(socket_path)
        server.last_activity = 0
        worker.join(1.2)
        assert worker.is_alive()
        assert _bridge_ready(socket_path)
    finally:
        client.terminate()
        client.wait(timeout=2)
        server.last_activity = 0
        worker.join(3)
    assert not worker.is_alive()
    assert not os.path.exists(socket_path)


@pytest.mark.parametrize("pid,environment,expected", [
    (0, "SODA_IDENTITY_BRIDGE_SOCKET=/run/user/1000/test.sock\x00", True),
    (0, "SODA_IDENTITY_BRIDGE_SOCKET=/run/user/1000/test.sock.other\x00", False),
    (0, "OTHER=SODA_IDENTITY_BRIDGE_SOCKET=/run/user/1000/test.sock\x00", False),
    (os.getpid(), "SODA_IDENTITY_BRIDGE_SOCKET=/run/user/1000/test.sock\x00", False),
])
def test_bridge_client_detection_requires_exact_marker(monkeypatch, pid, environment, expected):
    class Process:
        def get_env(self):
            return environment

    process = Process()
    process.pid = pid
    monkeypatch.setattr("bottles.backend.identity.ProcUtils.get_procs", lambda: [process])
    server = IdentityBridgeServer("/run/user/1000/test.sock", "test", Store())
    assert server._has_clients() is expected


def test_protocol_rejects_invalid_magic():
    encoded = bytearray(encode_message(Message(OP_PING, 1, 0, {})))
    encoded[:4] = (MAGIC + 1).to_bytes(4, "little")
    with pytest.raises(ProtocolError):
        decode_message(encoded)


def test_bridge_readiness_uses_protocol_ping():
    socket_path = os.path.join(
        os.environ["TMPDIR"], f"bridge-{time.time_ns()}.sock"
    )
    ready = threading.Event()

    def serve():
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(socket_path)
            listener.listen(1)
            ready.set()
            connection, _ = listener.accept()
            with connection:
                request = receive_message(connection)
                connection.sendall(
                    encode_message(
                        Message(
                            request.opcode | RESPONSE_BIT,
                            request.request_id,
                            STATUS_OK,
                            {},
                        )
                    )
                )

    thread = threading.Thread(target=serve)
    thread.start()
    assert ready.wait(1)
    assert _bridge_ready(socket_path)
    thread.join(1)
    assert not thread.is_alive()
    os.unlink(socket_path)


def test_bridge_readiness_rejects_stale_socket():
    socket_path = os.path.join(
        os.environ["TMPDIR"], f"bridge-{time.time_ns()}.sock"
    )
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(socket_path)

    assert not _bridge_ready(socket_path)
    os.unlink(socket_path)


def test_bridge_process_is_reaped(tmp_path, monkeypatch):
    reaped = threading.Event()

    class Process:
        def poll(self):
            return None

        def wait(self):
            reaped.set()

    monkeypatch.setattr("bottles.backend.identity.Paths.temp", str(tmp_path))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(
        "bottles.backend.identity.subprocess.Popen", lambda *_args, **_kwargs: Process()
    )
    monkeypatch.setattr("bottles.backend.identity._bridge_ready", lambda _path: True)

    socket_path = start_identity_bridge(f"context-{time.time_ns()}")

    assert socket_path
    assert reaped.wait(1)


@pytest.mark.parametrize("runtime", [False, True])
def test_bridge_starts_outside_package_directory(tmp_path, monkeypatch, runtime):
    monkeypatch.chdir(tmp_path)
    for name in ("PYTHONPATH", "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("bottles.backend.identity.Paths.temp", os.environ["TMPDIR"])
    if runtime:
        monkeypatch.setenv("XDG_RUNTIME_DIR", os.environ["TMPDIR"])
    context = f"context-{time.time_ns()}"
    socket_path = start_identity_bridge(context)
    try:
        assert socket_path
        assert _bridge_ready(socket_path)
    finally:
        bridge = _bridges.get(context)
        if bridge:
            bridge.process.terminate()
            bridge.process.wait(timeout=3)


def test_bridge_starts_with_long_data_path(tmp_path, monkeypatch):
    for name in ("DISPLAY", "WAYLAND_DISPLAY"):
        monkeypatch.delenv(name, raising=False)
    runtime = os.environ["TMPDIR"]
    data_path = str(tmp_path / ("data" * 30))
    monkeypatch.setenv("XDG_RUNTIME_DIR", runtime)
    monkeypatch.setattr("bottles.backend.identity.Paths.temp", data_path)
    context = f"context-{time.time_ns()}"
    socket_path = start_identity_bridge(context)
    try:
        assert socket_path
        assert socket_path.startswith(runtime + os.sep)
        assert _bridge_ready(socket_path)
        assert os.stat(os.path.dirname(socket_path)).st_mode & 0o777 == 0o700
        assert os.stat(socket_path).st_mode & 0o777 == 0o700
    finally:
        bridge = _bridges.get(context)
        if bridge:
            bridge.process.terminate()
            bridge.process.wait(timeout=3)


def test_live_bridge_is_reused_while_busy(monkeypatch):
    context = f"context-{time.time_ns()}"

    class Process:
        def poll(self):
            return None

    bridge = _BridgeProcess("/run/user/1000/bridge.sock", Process())
    monkeypatch.setitem(_bridges, context, bridge)
    monkeypatch.setattr(
        "bottles.backend.identity._bridge_ready",
        lambda _path: pytest.fail("a live broker must not be pinged"),
    )

    assert start_identity_bridge(context) == bridge.socket_path


def test_provider_rejects_control_characters_in_login_hint():
    with pytest.raises(ProtocolError):
        MicrosoftIdentityProvider._validate_request(
            "client", "organizations", "openid", "user@example.com\n"
        )


def test_authorization_uses_system_browser_and_pkce(monkeypatch):
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
    nonce = base64.urlsafe_b64encode(b"n" * 32).rstrip(b"=").decode()
    token = {
        "access_token": "access",
        "id_token": _id_token(client_id, nonce),
        "refresh_token": "refresh",
        "expires_in": 3600,
        "client_info": "client-info",
        "scope": "openid profile email",
    }
    opened = []
    session = Session([token])
    monkeypatch.setattr(
        "bottles.backend.identity.secrets.token_bytes",
        lambda size: b"n" * size if size == 32 else b"v" * size,
    )
    provider = MicrosoftIdentityProvider(
        Store(), session, opened.append, Listener
    )

    result = provider.authorize(
        client_id, "organizations", "openid profile offline_access", "user@example.com"
    )

    query = parse_qs(urlparse(opened[0]).query)
    assert query["redirect_uri"] == [
        "ms-appx-web://microsoft.aad.brokerplugin/" + client_id
    ]
    assert query["code_challenge_method"] == ["S256"]
    assert query["login_hint"] == ["user@example.com"]
    assert query["scope"] == ["openid profile email offline_access"]
    assert "code_verifier" not in query
    assert session.requests[0][1]["code_verifier"]
    assert session.requests[0][3] is False
    assert session.requests[0][1]["client_info"] == "1"
    assert result.access_token == "access"
    fields = result_fields(result)
    assert fields[FIELD_SCOPES] == b"openid profile email"
    assert fields[FIELD_CLIENT_INFO] == b"client-info"
    assert fields[FIELD_ID_TOKEN] == token["id_token"].encode()
    assert int(fields[FIELD_EXPIRES_AT]) > int(time.time())


@pytest.mark.parametrize("invalid", ["audience", "nonce"])
def test_invalid_id_token_is_not_stored_or_cached(monkeypatch, invalid):
    nonce = base64.urlsafe_b64encode(b"n" * 32).rstrip(b"=").decode()
    monkeypatch.setattr(
        "bottles.backend.identity.secrets.token_bytes", lambda size: b"n" * size
    )
    token = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": 3600,
        "id_token": _id_token(
            "other-client" if invalid == "audience" else "client",
            "other-nonce" if invalid == "nonce" else nonce,
        ),
    }
    store = Store()
    completed = []
    provider = MicrosoftIdentityProvider(
        store,
        Session([token]),
        lambda _uri: None,
        Listener,
        lambda success, message: completed.append((success, message)),
    )

    with pytest.raises(AuthenticationError, match=f"unexpected ID token {invalid}"):
        provider.authorize("client", "common", "openid", "")

    assert store.values == {}
    assert provider.cache == {}
    assert completed == [(False, f"unexpected ID token {invalid}")]


@pytest.mark.parametrize("audience,reason", (
    ("CLIENT", "client ID case mismatch"),
    ("private-account@example.invalid", "different client"),
    (["client", "private-token-value"], "audience list"),
    (None, "invalid audience type"),
    ({"private-token-value": "private-account@example.invalid"}, "invalid audience type"),
))
def test_audience_failure_logs_only_the_reason(monkeypatch, audience, reason):
    warnings = []
    monkeypatch.setattr(
        "bottles.backend.identity.logging.warning",
        lambda message, **_kwargs: warnings.append(message),
    )
    token = {
        "access_token": "private-access-token",
        "refresh_token": "private-refresh-token",
        "id_token": _id_token(audience),
        "expires_in": 3600,
    }

    with pytest.raises(AuthenticationError, match="unexpected ID token audience"):
        MicrosoftIdentityProvider._result_from_token(token, "client")

    assert warnings == [f"ID token audience rejected: {reason}"]


def test_office_ticket_uses_the_licensing_resource(monkeypatch):
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
    nonce = base64.urlsafe_b64encode(b"n" * 32).rstrip(b"=").decode()
    session = Session(
        [
            {
                "access_token": "access",
                "id_token": _id_token(client_id, nonce),
                "refresh_token": "refresh",
                "expires_in": 3600,
            }
        ]
    )
    opened = []
    monkeypatch.setattr(
        "bottles.backend.identity.secrets.token_bytes",
        lambda size: b"n" * size if size == 32 else b"v" * size,
    )
    provider = MicrosoftIdentityProvider(
        Store(), session, opened.append, Listener
    )

    provider.authorize(
        client_id,
        "common",
        "service::https://licensing.m365.svc.cloud.microsoft/::MBI_SSL_SHORT",
        "",
    )

    query = parse_qs(urlparse(opened[0]).query)
    assert query["scope"] == [
        "openid profile email offline_access "
        "https://licensing.m365.svc.cloud.microsoft/.default"
    ]


def test_telemetry_ticket_does_not_open_the_browser():
    opened = []
    provider = MicrosoftIdentityProvider(
        Store(), Session([]), opened.append, Listener
    )

    with pytest.raises(AuthenticationError, match="unsupported identity resource"):
        provider.authorize(
            "d3590ed6-52b3-4102-aeff-aad2292ab01c",
            "common",
            "https://events.data.microsoft.com/OneCollector/1.0/",
            "",
        )

    assert not opened


def test_authorization_reuses_the_current_account():
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"

    class CurrentStore(Store):
        def load(self, stored_client_id, account_id):
            if stored_client_id == client_id and not account_id:
                return {
                    "refresh_token": "old-refresh",
                    "id_token": _id_token(client_id),
                    "account_id": "account-id",
                }
            return super().load(stored_client_id, account_id)

    session = Session(
        [
            {
                "access_token": "new-access",
                "id_token": _id_token(client_id),
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            }
        ]
    )
    opened = []
    provider = MicrosoftIdentityProvider(
        CurrentStore(), session, opened.append, Listener
    )

    result = provider.authorize(
        client_id,
        "common",
        "service::https://licensing.m365.svc.cloud.microsoft/::MBI_SSL_SHORT",
        "",
    )

    assert result.access_token == "new-access"
    assert not opened


def test_cached_token_is_not_reused_for_a_different_authority():
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
    store = Store()
    store.values[(client_id, "account-id")] = {
        "refresh_token": "refresh",
        "id_token": _id_token(client_id),
    }
    session = Session([
        {
            "access_token": token,
            "id_token": _id_token(client_id),
            "refresh_token": "refresh",
            "expires_in": 3600,
        }
        for token in ["common-token", "tenant-token"]
    ])
    provider = MicrosoftIdentityProvider(store, session)

    common = provider.get_token(client_id, "common", "openid", "account-id")
    tenant = provider.get_token(
        client_id,
        "00000000-0000-0000-0000-000000000001",
        "openid",
        "account-id",
    )

    assert common.access_token == "common-token"
    assert tenant.access_token == "tenant-token"
    assert len(session.requests) == 2


def test_authorization_prompts_when_the_requested_account_changes(monkeypatch):
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
    nonce = base64.urlsafe_b64encode(b"n" * 32).rstrip(b"=").decode()

    class CurrentStore(Store):
        def load(self, _client_id, _account_id):
            return {
                "refresh_token": "old-refresh",
                "id_token": _id_token(client_id),
                "account_id": "account-id",
                "username": "user@example.com",
            }

    session = Session([
        {
            "access_token": "other-access",
            "id_token": _id_token(client_id, nonce, "other@example.com"),
            "refresh_token": "other-refresh",
            "expires_in": 3600,
        }
    ])
    opened = []
    monkeypatch.setattr(
        "bottles.backend.identity.secrets.token_bytes",
        lambda size: b"n" * size if size == 32 else b"v" * size,
    )
    provider = MicrosoftIdentityProvider(
        CurrentStore(), session, opened.append, Listener
    )

    result = provider.authorize(client_id, "common", "openid", "other@example.com")

    assert result.username == "other@example.com"
    assert len(opened) == 1
    assert session.requests[0][1]["grant_type"] == "authorization_code"


def test_identity_callback_is_forwarded_to_the_waiting_listener(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr("bottles.backend.identity.Paths.temp", str(tmp_path))
    state = "s" * 43
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
    listener = RedirectListener(state, client_id)
    result = []
    thread = threading.Thread(target=lambda: result.append(listener.wait(2)))
    thread.start()

    uri = f"{listener.redirect_uri}?code=authorization-code&state={state}"
    assert forward_identity_callback(uri)
    thread.join(2)

    assert not thread.is_alive()
    assert result == [
        {
            "code": "authorization-code",
            "error": None,
            "error_description": None,
        }
    ]
    assert not os.path.exists(listener.socket_path)


def test_identity_callback_forwards_the_activation_token(monkeypatch, tmp_path):
    monkeypatch.setattr("bottles.backend.identity.Paths.temp", str(tmp_path))
    state = "s" * 43
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
    activation_tokens = []
    listener = RedirectListener(
        state,
        client_id,
        activation_callback=activation_tokens.append,
    )
    result = []
    thread = threading.Thread(target=lambda: result.append(listener.wait(2)))
    thread.start()

    uri = f"{listener.redirect_uri}?code=authorization-code&state={state}"
    assert forward_identity_callback(uri, "activation/token+value==")
    thread.join(2)

    assert not thread.is_alive()
    assert activation_tokens == ["activation/token+value=="]
    assert result == [
        {
            "code": "authorization-code",
            "error": None,
            "error_description": None,
        }
    ]


@pytest.mark.parametrize("activation_token", ["token\nvalue", "t" * 4097])
def test_identity_callback_rejects_an_invalid_activation_token(
    activation_token,
):
    state = "s" * 43
    uri = (
        "ms-appx-web://microsoft.aad.brokerplugin/"
        "d3590ed6-52b3-4102-aeff-aad2292ab01c"
        f"?code=authorization-code&state={state}"
    )

    assert not forward_identity_callback(uri, activation_token)


def test_identity_callback_rejects_an_embedded_activation_token():
    state = "s" * 43
    uri = (
        "ms-appx-web://microsoft.aad.brokerplugin/"
        "d3590ed6-52b3-4102-aeff-aad2292ab01c"
        f"?code=authorization-code&state={state}"
        "&_bottles_activation_token=spoofed"
    )

    assert not forward_identity_callback(uri, "trusted")


def test_identity_callback_forwards_an_authorization_error(monkeypatch, tmp_path):
    monkeypatch.setattr("bottles.backend.identity.Paths.temp", str(tmp_path))
    state = "s" * 43
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
    listener = RedirectListener(state, client_id)
    result = []
    thread = threading.Thread(target=lambda: result.append(listener.wait(2)))
    thread.start()

    uri = (
        f"{listener.redirect_uri}?error=access_denied&"
        f"error_description=Sign-in+was+canceled&state={state}"
    )
    assert forward_identity_callback(uri)
    thread.join(2)

    assert not thread.is_alive()
    assert result == [
        {
            "code": None,
            "error": "access_denied",
            "error_description": "Sign-in was canceled",
        }
    ]


def test_identity_callback_rejects_a_different_client(monkeypatch, tmp_path):
    monkeypatch.setattr("bottles.backend.identity.Paths.temp", str(tmp_path))
    state = "s" * 43
    cancel_event = threading.Event()
    listener = RedirectListener(
        state,
        "d3590ed6-52b3-4102-aeff-aad2292ab01c",
        cancel_event,
    )
    canceled = []

    def wait():
        try:
            listener.wait(2)
        except AuthenticationCanceled:
            canceled.append(True)

    thread = threading.Thread(target=wait)
    thread.start()
    uri = (
        "ms-appx-web://microsoft.aad.brokerplugin/"
        f"00000000-0000-0000-0000-000000000000?code=code&state={state}"
    )

    assert not forward_identity_callback(uri)
    cancel_event.set()
    thread.join(2)

    assert not thread.is_alive()
    assert canceled == [True]


@pytest.mark.parametrize(
    "result",
    [
        "code=first&code=second",
        "error=first&error=second",
        "code=authorization-code&error=access_denied",
        "",
    ],
)
def test_identity_callback_rejects_an_ambiguous_result(
    monkeypatch, tmp_path, result
):
    monkeypatch.setattr("bottles.backend.identity.Paths.temp", str(tmp_path))
    state = "s" * 43
    cancel_event = threading.Event()
    listener = RedirectListener(
        state,
        "d3590ed6-52b3-4102-aeff-aad2292ab01c",
        cancel_event,
    )
    canceled = []

    def wait():
        try:
            listener.wait(2)
        except AuthenticationCanceled:
            canceled.append(True)

    thread = threading.Thread(target=wait)
    thread.start()
    separator = "&" if result else ""
    uri = f"{listener.redirect_uri}?state={state}{separator}{result}"

    assert not forward_identity_callback(uri)
    cancel_event.set()
    thread.join(2)

    assert not thread.is_alive()
    assert canceled == [True]


def test_identity_callback_crosses_isolated_runtime_directories(
    monkeypatch, tmp_path
):
    data_path = tmp_path / ("long-data-directory-" * 6)
    monkeypatch.setattr("bottles.backend.identity.Paths.temp", str(data_path))
    state = "s" * 43
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
    listener = RedirectListener(state, client_id)
    assert len(listener.socket_path.encode()) > 107
    result = []
    thread = threading.Thread(target=lambda: result.append(listener.wait(3)))
    thread.start()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "other-runtime"))

    uri = f"{listener.redirect_uri}?code=authorization-code&state={state}"
    assert forward_identity_callback(uri)
    thread.join(3)

    assert not thread.is_alive()
    assert result == [
        {
            "code": "authorization-code",
            "error": None,
            "error_description": None,
        }
    ]


def test_identity_callback_requires_a_waiting_listener(monkeypatch, tmp_path):
    monkeypatch.setattr("bottles.backend.identity.Paths.temp", str(tmp_path))
    state = "s" * 43
    uri = (
        "ms-appx-web://microsoft.aad.brokerplugin/"
        "d3590ed6-52b3-4102-aeff-aad2292ab01c"
        f"?code=authorization-code&state={state}"
    )

    assert not forward_identity_callback(uri)


def test_authorization_fails_when_the_browser_cannot_open():
    def fail(_uri):
        raise OSError("no browser")

    provider = MicrosoftIdentityProvider(Store(), Session([]), fail, Listener)

    with pytest.raises(AuthenticationError, match="unable to open"):
        provider.authorize(
            "d3590ed6-52b3-4102-aeff-aad2292ab01c",
            "organizations",
            "openid profile offline_access",
            "",
        )


def test_refresh_rotates_the_stored_token():
    client_id = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
    store = Store()
    store.values[(client_id, "account-id")] = {
        "refresh_token": "old-refresh",
        "id_token": _id_token(client_id),
    }
    session = Session(
        [
            {
                "access_token": "new-access",
                "id_token": _id_token(client_id),
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            }
        ]
    )
    provider = MicrosoftIdentityProvider(store, session, lambda _uri: None)

    result = provider.get_token(
        client_id, "organizations", "openid profile", "account-id"
    )

    assert result.access_token == "new-access"
    assert store.values[(client_id, "account-id")]["refresh_token"] == "new-refresh"
    assert session.requests[0][1]["refresh_token"] == "old-refresh"
    assert session.requests[0][1]["client_info"] == "1"


def test_server_dispatches_authorization_without_exposing_refresh_token():
    result = AuthorizationResult(
        "access",
        "id",
        "refresh",
        int(time.time()) + 3600,
        "account-id",
        "user@example.com",
        "Test",
        "User",
        "Test User",
        "tenant-id",
        "client-info",
    )

    class Provider:
        def authorize(self, *_args):
            return result

    server = IdentityBridgeServer("/unused", "context", Provider())
    response = server.dispatch(
        Message(
            OP_AUTHORIZE,
            4,
            0,
            {
                FIELD_CLIENT_ID: b"client",
                FIELD_AUTHORITY: b"organizations",
                FIELD_SCOPES: b"openid",
                FIELD_LOGIN_HINT: b"",
                FIELD_POLICY: b"JWT",
            },
        )
    )
    assert response.opcode == OP_AUTHORIZE | RESPONSE_BIT
    assert response.status == STATUS_OK
    assert response.fields[FIELD_ACCESS_TOKEN] == b"access"
    assert response.fields[FIELD_ID_TOKEN] == b"id"
    assert b"refresh" not in encode_message(response)


def test_server_resolves_office_caller_id():
    result = AuthorizationResult(
        "access",
        "id",
        "refresh",
        int(time.time()) + 3600,
        "account-id",
        "user@example.com",
        "Test",
        "User",
        "Test User",
        "tenant-id",
        "client-info",
    )
    calls = []

    class Provider:
        def authorize(self, *args):
            calls.append(args)
            return result

    server = IdentityBridgeServer("/unused", "context", Provider())
    response = server.dispatch(
        Message(
            OP_AUTHORIZE,
            4,
            0,
            {
                FIELD_CALLER_ID: b"2B379600-B42B-4FE9-A59C-A312FB934935",
                FIELD_AUTHORITY: b"common",
                FIELD_SCOPES: b"openid",
                FIELD_LOGIN_HINT: b"",
                FIELD_POLICY: b"JWT",
            },
        )
    )

    assert response.status == STATUS_OK
    assert calls[0][0] == "d3590ed6-52b3-4102-aeff-aad2292ab01c"


def test_server_rejects_ambiguous_identity_fields():
    server = IdentityBridgeServer("/unused", "context", object())
    response = server.dispatch(
        Message(
            OP_AUTHORIZE,
            4,
            0,
            {
                FIELD_CALLER_ID: b"2b379600-b42b-4fe9-a59c-a312fb934935",
                FIELD_CLIENT_ID: b"d3590ed6-52b3-4102-aeff-aad2292ab01c",
                FIELD_SCOPES: b"openid",
            },
        )
    )

    assert response.status == STATUS_INVALID_REQUEST


def test_server_dispatches_cached_token_without_exposing_refresh_token():
    result = AuthorizationResult(
        "access",
        "id",
        "refresh",
        int(time.time()) + 3600,
        "account-id",
        "user@example.com",
        "Test",
        "User",
        "Test User",
        "tenant-id",
        "client-info",
    )

    class Provider:
        def get_token(self, *_args):
            return result

    server = IdentityBridgeServer("/unused", "context", Provider())
    response = server.dispatch(
        Message(
            OP_GET_TOKEN,
            5,
            0,
            {
                FIELD_CLIENT_ID: b"client",
                FIELD_AUTHORITY: b"organizations",
                FIELD_SCOPES: b"openid",
                FIELD_ACCOUNT_ID: b"account-id",
            },
        )
    )
    assert response.opcode == OP_GET_TOKEN | RESPONSE_BIT
    assert response.status == STATUS_OK
    assert response.fields[FIELD_ACCESS_TOKEN] == b"access"
    assert response.fields[FIELD_ACCOUNT_ID] == b"account-id"
    assert b"refresh" not in encode_message(response)


def test_server_rejects_missing_authorization_fields():
    server = IdentityBridgeServer("/unused", "context", object())
    response = server.dispatch(Message(OP_AUTHORIZE, 8, 0, {}))
    assert response.status == STATUS_INVALID_REQUEST
    assert FIELD_ERROR in response.fields


def test_server_rejects_unexpected_fields():
    server = IdentityBridgeServer("/unused", "context", object())
    response = server.dispatch(
        Message(OP_GET_TOKEN, 9, 0, {FIELD_CLIENT_ID: b"client", FIELD_ERROR: b"x"})
    )
    assert response.status == STATUS_INVALID_REQUEST
    assert FIELD_ERROR in response.fields


def test_secret_store_tracks_the_current_account(monkeypatch):
    values = {}

    def store_secret(_schema, attributes, _collection, _label, value, _cancellable):
        values[tuple(sorted(attributes.items()))] = value
        return True

    def lookup_secret(_schema, attributes, _cancellable):
        return values.get(tuple(sorted(attributes.items())))

    def clear_secret(_schema, attributes, _cancellable):
        return values.pop(tuple(sorted(attributes.items())), None) is not None

    monkeypatch.setattr(
        "bottles.backend.identity.Secret.password_store_sync", store_secret
    )
    monkeypatch.setattr(
        "bottles.backend.identity.Secret.password_lookup_sync", lookup_secret
    )
    monkeypatch.setattr(
        "bottles.backend.identity.Secret.password_clear_sync", clear_secret
    )
    result = AuthorizationResult(
        "access",
        "id",
        "refresh",
        int(time.time()) + 3600,
        "account-id",
        "user@example.com",
        "Test",
        "User",
        "Test User",
        "tenant-id",
        "client-info",
    )
    store = SecretTokenStore("context")

    store.store("client", result)

    assert store.load("client", "")["refresh_token"] == "refresh"
    assert store.clear("client", "")
    assert store.load("client", "") is None


def test_secret_store_enumerates_scoped_accounts(monkeypatch):
    from bottles.backend.identity import PERSONAL_TENANT

    class Item:
        def __init__(self, context, client, account, tenant):
            self.attributes = {"context": context, "client": client, "account": account}
            self.value = {
                "account_id": account, "username": account + "@example.com",
                "tenant_id": tenant, "refresh_token": "secret",
            }

        def get_attributes(self):
            return self.attributes

        def retrieve_secret_sync(self, _cancellable):
            return self

        def get_text(self):
            return json.dumps(self.value)

    items = [
        Item("context", "client", "business", "tenant-id"),
        Item("context", "client", "personal", PERSONAL_TENANT),
        Item("context", "client", "__current__", ""),
        Item("context", "other", "another", "tenant-id"),
        Item("outside", "client", "hidden", "tenant-id"),
    ]
    queries = []

    def search(_schema, attributes, _flags, _cancellable):
        queries.append(attributes)
        return [item for item in items if all(
            item.attributes.get(key) == value for key, value in attributes.items()
        )]

    monkeypatch.setattr("bottles.backend.identity.Secret.password_search_sync", search)
    store = SecretTokenStore("context")
    assert store.accounts("client", "organizations") == [("business", "business@example.com")]
    assert store.accounts("client", "consumers") == [("personal", "personal@example.com")]
    assert len(store.accounts("client", "common")) == 2
    assert len(store.accounts("", "common")) == 3
    assert store.accounts("missing", "common") == []
    assert store.accounts("client", "other-tenant") == []
    assert queries[0] == {"context": "context", "client": "client"}
    items[0].value.pop("refresh_token")
    with pytest.raises(AuthenticationStorageError):
        store.accounts("client", "common")


def test_account_enumeration_returns_metadata_only():
    class AccountStore:
        def accounts(self, client, authority):
            assert client == "d3590ed6-52b3-4102-aeff-aad2292ab01c"
            assert authority == "common"
            return [("account-id", "user@example.com")]

    class Provider:
        store = AccountStore()

    server = IdentityBridgeServer("unused", "context", Provider())
    response = server.dispatch(Message(OP_LIST_ACCOUNTS, 3, 0, {
        FIELD_CLIENT_ID: b"2b379600-b42b-4fe9-a59c-a312fb934935",
        FIELD_AUTHORITY: b"common",
    }))
    assert response.status == STATUS_OK
    assert response.fields == {FIELD_ACCOUNTS: (
        struct.pack("<II", 1, 10) + b"account-id"
        + struct.pack("<I", 16) + b"user@example.com"
    )}
    assert b"refresh" not in encode_message(response)
    for fields in (
        {FIELD_CLIENT_ID: b"invalid/client"},
        {FIELD_AUTHORITY: b"https://evil.example"},
        {FIELD_ACCESS_TOKEN: b"unexpected"},
    ):
        response = server.dispatch(Message(OP_LIST_ACCOUNTS, 4, 0, fields))
        assert response.status == STATUS_INVALID_REQUEST


def test_cpak_store_uses_only_the_scoped_shim(monkeypatch):
    monkeypatch.setenv("CPAK_CONTAINER_ID", "synthetic")
    values = {}

    def request(args, **kwargs):
        assert args == ["cpak-secrets"]
        assert kwargs["stderr"] == subprocess.PIPE
        data = json.loads(kwargs["input"])
        attrs = data["attributes"]
        key = tuple(sorted(attrs.items()))
        assert attrs["context"] == "test-context"
        entries = []
        changed = False
        if data["operation"] == "put":
            values[key] = data["value"]
            changed = True
        elif data["operation"] == "delete":
            changed = values.pop(key, None) is not None
        else:
            entries = [
                {"attributes": dict(stored), "value": value}
                for stored, value in values.items()
                if all(dict(stored).get(k) == v for k, v in attrs.items())
            ]
        return subprocess.CompletedProcess(args, 0, json.dumps({
            "entries": entries, "changed": changed,
        }))

    def forbidden(*args):
        pytest.fail("cpak attempted direct keyring access")

    monkeypatch.setattr("bottles.backend.identity.subprocess.run", request)
    for name in ("password_store_sync", "password_lookup_sync",
                 "password_clear_sync", "password_search_sync"):
        monkeypatch.setattr("bottles.backend.identity.Secret." + name, forbidden)
    result = AuthorizationResult(
        "access", "id", "refresh", int(time.time()) + 3600,
        "account-id", "user@example.com", "Test", "User", "Test User",
        "tenant-id", "client-info",
    )
    store = SecretTokenStore("test-context")
    store.store("client", result)
    assert store.load("client", "")["refresh_token"] == "refresh"
    assert store.accounts("client", "organizations") == [("account-id", "user@example.com")]
    assert store.clear("client", "")
    assert store.load("client", "") is None


@pytest.mark.parametrize("failure", ("missing-shim", "denied", "scope", "malformed", "private-stderr"))
def test_cpak_keyring_failure_never_falls_back_to_host_bus(monkeypatch, failure):
    monkeypatch.setenv("CPAK_CONTAINER_ID", "synthetic")

    warnings = []

    def request(args, **kwargs):
        if failure == "missing-shim":
            raise FileNotFoundError()
        if failure == "denied":
            raise subprocess.CalledProcessError(
                1,
                args,
                stderr="secure credential storage is unavailable or locked",
            )
        if failure == "private-stderr":
            raise subprocess.CalledProcessError(
                1,
                args,
                stderr="account@example.invalid token=private-token-value",
            )
        if failure == "malformed":
            return subprocess.CompletedProcess(args, 0, "[]")
        return subprocess.CompletedProcess(args, 0, json.dumps({
            "changed": False,
            "entries": [{"attributes": {"context": "other"}, "value": "synthetic"}],
        }))

    def forbidden(*args):
        pytest.fail("cpak fell back to direct keyring access")

    monkeypatch.setattr("bottles.backend.identity.subprocess.run", request)
    monkeypatch.setattr("bottles.backend.identity.logging.warning", warnings.append)
    monkeypatch.setattr("bottles.backend.identity.Secret.password_lookup_sync", forbidden)
    with pytest.raises(AuthenticationStorageError):
        SecretTokenStore("context").load("client", "account")
    assert len(warnings) == 1
    assert "synthetic" not in warnings[0]
    assert "account@example.invalid" not in warnings[0]
    assert "private-token-value" not in warnings[0]
    if failure == "denied":
        assert warnings == [
            "cpak credential broker failed: secure credential storage is unavailable or locked"
        ]
