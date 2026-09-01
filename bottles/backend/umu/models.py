from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

CURRENT_SCHEMA_VERSION = 1
UMU_STORE_IDS = (
    "none",
    "amazon",
    "battlenet",
    "ea",
    "egs",
    "gog",
    "humble",
    "itchio",
    "steam",
    "ubisoft",
    "umu",
    "zoomplatform",
)
UmuGameState = Literal["draft", "installing", "ready", "failed", "stopped"]
_GAME_STATES = {"draft", "installing", "ready", "failed", "stopped"}


class UmuModelError(ValueError):
    pass


class UnsupportedUmuSchemaError(UmuModelError):
    pass


def _clean_text(value: object, field_name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise UmuModelError(f"Invalid {field_name}")
    if "\0" in value:
        raise UmuModelError(f"Invalid {field_name}")
    return value


def _clean_environment(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise UmuModelError("Invalid environment")

    environment = {}
    for key, item in value.items():
        clean_key = _clean_text(key, "environment key")
        if "=" in clean_key:
            raise UmuModelError("Invalid environment key")
        environment[clean_key] = _clean_text(
            item, "environment value", allow_empty=True
        )
    return environment


@dataclass(frozen=True)
class UmuPrefix:
    path: str
    managed: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "path", _clean_text(self.path, "prefix path"))
        if not isinstance(self.managed, bool):
            raise UmuModelError("Invalid managed prefix flag")
        if not isinstance(self.extra, Mapping):
            raise UmuModelError("Invalid prefix metadata")
        object.__setattr__(self, "extra", deepcopy(dict(self.extra)))

    def resolve(self, data_root: str | Path) -> Path:
        root = Path(data_root).expanduser().resolve(strict=False)
        path = Path(self.path).expanduser()

        if self.managed:
            if path.is_absolute():
                raise UmuModelError("Managed prefix paths must be relative")
            resolved = (root / path).resolve(strict=False)
            try:
                resolved.relative_to(root)
            except ValueError as error:
                raise UmuModelError(
                    "Managed prefix path escapes the UMU data root"
                ) from error
            return resolved

        if not path.is_absolute():
            raise UmuModelError("Custom prefix paths must be absolute")
        return path.resolve(strict=False)

    @classmethod
    def from_dict(cls, data: object) -> "UmuPrefix":
        if not isinstance(data, Mapping):
            raise UmuModelError("Invalid prefix")
        values = deepcopy(dict(data))
        path = values.pop("path", None)
        managed = values.pop("managed", True)
        return cls(path=path, managed=managed, extra=values)

    def to_dict(self) -> dict[str, Any]:
        data = deepcopy(self.extra)
        data.update({"path": self.path, "managed": self.managed})
        return data


@dataclass(frozen=True)
class UmuGame:
    id: UUID
    name: str
    executable: Path
    prefix: UmuPrefix
    proton: str
    state: UmuGameState = "draft"
    game_id: str = "umu-default"
    store: str = "none"
    arguments: tuple[str, ...] = ()
    working_directory: Path | None = None
    environment: dict[str, str] = field(default_factory=dict)
    sandbox: bool = False
    share_net: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        try:
            game_uuid = self.id if isinstance(self.id, UUID) else UUID(str(self.id))
        except (TypeError, ValueError, AttributeError) as error:
            raise UmuModelError("Invalid game id") from error
        object.__setattr__(self, "id", game_uuid)
        object.__setattr__(self, "name", _clean_text(self.name, "game name"))

        if not isinstance(self.executable, (str, Path)):
            raise UmuModelError("Invalid executable")
        executable = _clean_text(str(self.executable), "executable")
        executable_path = Path(executable).expanduser()
        if not executable_path.is_absolute():
            raise UmuModelError("Executable path must be absolute")
        object.__setattr__(self, "executable", executable_path)

        if not isinstance(self.prefix, UmuPrefix):
            raise UmuModelError("Invalid prefix")
        object.__setattr__(self, "proton", _clean_text(self.proton, "Proton path"))
        if not isinstance(self.state, str) or self.state not in _GAME_STATES:
            raise UmuModelError("Invalid game state")
        object.__setattr__(self, "game_id", _clean_text(self.game_id, "UMU game id"))
        store = _clean_text(self.store, "store")
        if store not in UMU_STORE_IDS:
            raise UmuModelError("Invalid store")
        object.__setattr__(self, "store", store)

        if not isinstance(self.arguments, (list, tuple)):
            raise UmuModelError("Invalid arguments")
        arguments = tuple(
            _clean_text(item, "argument", allow_empty=True) for item in self.arguments
        )
        object.__setattr__(self, "arguments", arguments)

        if self.working_directory in (None, ""):
            object.__setattr__(self, "working_directory", None)
        else:
            if not isinstance(self.working_directory, (str, Path)):
                raise UmuModelError("Invalid working directory")
            working_directory = _clean_text(
                str(self.working_directory), "working directory"
            )
            working_directory_path = Path(working_directory).expanduser()
            if not working_directory_path.is_absolute():
                raise UmuModelError("Working directory path must be absolute")
            object.__setattr__(self, "working_directory", working_directory_path)

        object.__setattr__(self, "environment", _clean_environment(self.environment))
        if not isinstance(self.sandbox, bool):
            raise UmuModelError("Invalid dedicated sandbox flag")
        if not isinstance(self.share_net, bool):
            raise UmuModelError("Invalid network sharing flag")
        if not isinstance(self.extra, Mapping):
            raise UmuModelError("Invalid game metadata")
        object.__setattr__(self, "extra", deepcopy(dict(self.extra)))

    @property
    def library_id(self) -> str:
        return f"umu:{self.id}"

    @classmethod
    def from_dict(cls, data: object) -> "UmuGame":
        if not isinstance(data, Mapping):
            raise UmuModelError("Invalid game configuration")
        values = deepcopy(dict(data))
        schema_version = values.pop("schema_version", CURRENT_SCHEMA_VERSION)
        if not isinstance(schema_version, int) or isinstance(schema_version, bool):
            raise UmuModelError("Invalid schema version")
        if schema_version != CURRENT_SCHEMA_VERSION:
            raise UnsupportedUmuSchemaError(
                f"Unsupported UMU game schema version: {schema_version}"
            )

        known = {
            "id": values.pop("id", None),
            "name": values.pop("name", None),
            "executable": values.pop("executable", None),
            "prefix": UmuPrefix.from_dict(values.pop("prefix", None)),
            "proton": values.pop("proton", None),
            "state": values.pop("state", "draft"),
            "game_id": values.pop("game_id", "umu-default"),
            "store": values.pop("store", "none"),
            "arguments": values.pop("arguments", ()),
            "working_directory": values.pop("working_directory", None),
            "environment": values.pop("environment", {}),
            "sandbox": values.pop("sandbox", False),
            "share_net": values.pop("share_net", False),
        }
        return cls(**known, extra=values)

    def to_dict(self) -> dict[str, Any]:
        data = deepcopy(self.extra)
        data.update(
            {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "id": str(self.id),
                "name": self.name,
                "executable": str(self.executable),
                "prefix": self.prefix.to_dict(),
                "proton": self.proton,
                "state": self.state,
                "game_id": self.game_id,
                "store": self.store,
                "arguments": list(self.arguments),
                "working_directory": (
                    str(self.working_directory) if self.working_directory else None
                ),
                "environment": dict(self.environment),
                "sandbox": self.sandbox,
                "share_net": self.share_net,
            }
        )
        return data
