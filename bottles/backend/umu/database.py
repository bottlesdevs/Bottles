import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from bottles.backend.umu.models import UMU_STORE_IDS

UMU_DATABASE_API = "https://umu.openwinecomponents.org/umu_api.php"
UMU_DATABASE_SOURCE = "https://github.com/Open-Wine-Components/umu-database"
UMU_DATABASE_LICENSE = "GPL-3.0"
_CACHE_MAX_AGE = 24 * 60 * 60
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class UmuDatabaseError(RuntimeError):
    pass


def _text(value, field, *, required=False):
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"Invalid UMU database {field}")
    value = value.strip()
    if required and not value:
        raise ValueError(f"Invalid UMU database {field}")
    if "\0" in value or len(value) > 4096:
        raise ValueError(f"Invalid UMU database {field}")
    return value


@dataclass(frozen=True)
class UmuDatabaseEntry:
    title: str
    store: str
    codename: str
    umu_id: str
    acronym: str = ""
    notes: str = ""
    executable_pattern: str = ""

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise TypeError("Invalid UMU database entry")
        store = _text(value.get("store"), "store", required=True).lower()
        if store not in UMU_STORE_IDS:
            raise ValueError("Invalid UMU database store")
        return cls(
            title=_text(value.get("title"), "title", required=True),
            store=store,
            codename=_text(value.get("codename"), "codename", required=True),
            umu_id=_text(value.get("umu_id"), "game ID", required=True),
            acronym=_text(value.get("acronym"), "acronym"),
            notes=_text(value.get("notes"), "notes"),
            executable_pattern=_text(
                value.get("exe_string", value.get("executable_pattern")),
                "executable pattern",
            ),
        )

    @property
    def search_text(self):
        return (
            f"{self.title} {self.store} {self.codename} {self.umu_id} "
            f"{self.acronym} {self.notes} {self.executable_pattern}"
        ).casefold()


class UmuDatabaseClient:
    def __init__(self, cache_path, opener=None, clock=None):
        self.cache_path = Path(cache_path)
        self._opener = opener or urllib.request.urlopen
        self._clock = clock or time.time
        self._entries = None

    def get_entries(self, refresh=False):
        if self._entries is not None and not refresh:
            return self._entries

        cached = self._read_cache()
        if not refresh and cached and self._cache_is_fresh():
            self._entries = cached
            return cached

        try:
            entries = self._download()
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as error:
            if cached:
                self._entries = cached
                return cached
            raise UmuDatabaseError("The UMU database could not be loaded.") from error

        self._entries = entries
        self._write_cache(entries)
        return entries

    def search(self, query, limit=50):
        terms = tuple(part for part in query.casefold().split() if part)
        if not terms:
            return []

        matches = [
            entry
            for entry in self.get_entries()
            if all(term in entry.search_text for term in terms)
        ]
        query_text = " ".join(terms)
        matches.sort(
            key=lambda entry: (
                entry.title.casefold() != query_text,
                not entry.title.casefold().startswith(query_text),
                entry.title.casefold(),
                entry.store,
            )
        )
        return matches[:limit]

    def _download(self):
        request = urllib.request.Request(
            UMU_DATABASE_API,
            headers={"Accept": "application/json", "User-Agent": "Bottles"},
        )
        with self._opener(request, timeout=15) as response:
            payload = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise ValueError("UMU database response is too large")
        return self._parse(json.loads(payload.decode("utf-8")))

    @staticmethod
    def _parse(payload):
        if not isinstance(payload, list):
            raise TypeError("Invalid UMU database response")
        entries = []
        for value in payload:
            try:
                entries.append(UmuDatabaseEntry.from_dict(value))
            except (TypeError, ValueError):
                continue
        if not entries:
            raise ValueError("The UMU database response contains no valid entries")
        return tuple(entries)

    def _cache_is_fresh(self):
        try:
            return self._clock() - self.cache_path.stat().st_mtime < _CACHE_MAX_AGE
        except OSError:
            return False

    def _read_cache(self):
        try:
            with self.cache_path.open(encoding="utf-8") as stream:
                return self._parse(json.load(stream))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return ()

    def _write_cache(self, entries):
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_path.with_suffix(".tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump([asdict(entry) for entry in entries], stream)
            temporary.replace(self.cache_path)
        except OSError:
            return
