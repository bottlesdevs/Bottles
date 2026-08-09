from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bottles.backend.models.result import Result
from bottles.backend.utils.steam import SteamUtils

AUTO_PROTON_VALUES = ("UMU-Proton", "GE-Proton")
DEFAULT_PROTON_VALUE = "ProtoSoda"
PROTOSODA_PREFIX = "protosoda-"


@dataclass(frozen=True)
class UmuProtonChoice:
    key: str
    title: str
    value: str | None
    source: Literal["auto", "bottles", "steam"]
    component_name: str | None = None
    installed: bool = False
    downloadable: bool = False
    channel: str | None = None


class UmuProtonCatalog:
    def __init__(self, manager):
        self.manager = manager

    @staticmethod
    def _runner_path(component_name):
        from bottles.backend.utils.manager import ManagerUtils

        return ManagerUtils.get_runner_path(component_name)

    @staticmethod
    def validate_value(value: str) -> str:
        if value in AUTO_PROTON_VALUES:
            return value
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Select a Proton version")

        path = Path(value).expanduser()
        if not path.is_absolute() or not path.is_dir():
            raise ValueError("The selected Proton version is not installed")
        try:
            is_proton = SteamUtils.is_proton(str(path))
        except (OSError, ValueError, TypeError):
            is_proton = False
        if not is_proton:
            raise ValueError(
                "The selected directory is not a Proton compatibility tool"
            )
        return str(path.resolve())

    @staticmethod
    def validate_selection(value: str) -> str:
        if value == DEFAULT_PROTON_VALUE:
            return value
        return UmuProtonCatalog.validate_value(value)

    def _latest_protosoda(self) -> str | None:
        catalog = self.manager.supported_proton_runners
        installed = {
            name
            for name in self.manager.runners_available
            if name.startswith(PROTOSODA_PREFIX)
        }
        names = {
            name
            for name, metadata in catalog.items()
            if name.startswith(PROTOSODA_PREFIX)
            and metadata.get("Channel") == "stable"
            and (
                self.manager.utils_conn.status
                or metadata.get("Cached", False)
                or name in installed
            )
        }

        def version(name):
            parts = (
                name.removeprefix(PROTOSODA_PREFIX).replace("-", ".").split(".")
            )
            if not all(part.isdigit() for part in parts):
                return None
            return tuple(int(part) for part in parts)

        if not names:
            names = {
                name
                for name in installed
                if version(name) is not None
                and catalog.get(name, {}).get("Channel") not in ("rc", "unstable")
            }
        return max(
            names,
            key=version,
            default=None,
        )

    def pin_value(self, value: str) -> str:
        if value != DEFAULT_PROTON_VALUE:
            return value
        component_name = self._latest_protosoda()
        if component_name is None:
            raise ValueError("ProtoSoda is not available from Bottles Components")
        return component_name

    def resolve_value(self, value: str) -> str:
        value = self.pin_value(value)
        if not value.startswith(PROTOSODA_PREFIX):
            return self.validate_value(value)

        try:
            return self.validate_value(self._runner_path(value))
        except ValueError:
            pass
        result = self.install(value)
        if not result.ok:
            raise ValueError(result.message or "ProtoSoda installation failed")
        return result.data.value

    def list_choices(
        self, query: str = "", *, include_unstable: bool = False
    ) -> list[UmuProtonChoice]:
        protosoda = self._latest_protosoda()
        choices = [
            UmuProtonChoice(
                key="auto:protosoda",
                title="ProtoSoda",
                value=DEFAULT_PROTON_VALUE,
                source="bottles",
                component_name=protosoda,
                installed=bool(
                    protosoda and protosoda in self.manager.runners_available
                ),
                downloadable=bool(protosoda),
                channel="stable",
            ),
            UmuProtonChoice(
                key="auto:umu-proton",
                title="UMU-Proton",
                value="UMU-Proton",
                source="auto",
                installed=True,
            ),
            UmuProtonChoice(
                key="auto:ge-proton",
                title="GE-Proton (Latest)",
                value="GE-Proton",
                source="auto",
                installed=True,
            ),
        ]
        installed = {}
        for name in self.manager.runners_available:
            if name.startswith("sys-"):
                continue
            path = self._runner_path(name)
            try:
                value = self.validate_value(path)
            except ValueError:
                continue
            source = "steam" if name in self.manager.external_runners else "bottles"
            installed[name] = UmuProtonChoice(
                key=f"{source}:{name}",
                title=name,
                value=value,
                source=source,
                component_name=name,
                installed=True,
            )

        catalog = self.manager.supported_proton_runners
        for name, metadata in catalog.items():
            if name == protosoda:
                continue
            channel = metadata.get("Channel")
            if channel in ("rc", "unstable") and not include_unstable:
                continue
            if name in installed:
                choice = installed.pop(name)
                choices.append(
                    UmuProtonChoice(
                        **{
                            **choice.__dict__,
                            "downloadable": True,
                            "channel": channel,
                        }
                    )
                )
                continue
            choices.append(
                UmuProtonChoice(
                    key=f"bottles:{name}",
                    title=name,
                    value=None,
                    source="bottles",
                    component_name=name,
                    downloadable=bool(
                        self.manager.utils_conn.status or metadata.get("Cached", False)
                    ),
                    channel=channel,
                )
            )

        choices.extend(installed.values())
        terms = query.strip().casefold()
        if terms:
            choices = [
                choice
                for choice in choices
                if terms
                in " ".join(
                    filter(
                        None,
                        (choice.title, choice.component_name, choice.value),
                    )
                ).casefold()
            ]
        return choices

    def install(self, component_name, func=None, cancel_event=None):
        if component_name not in self.manager.supported_proton_runners:
            return Result(False, message="Unknown Proton component")

        path = self._runner_path(component_name)
        try:
            value = self.validate_value(path)
        except ValueError:
            result = self.manager.component_manager.install(
                "runner:proton",
                component_name,
                func=func,
                cancel_event=cancel_event,
            )
            if not result.ok:
                return Result(False, message=result.message)
            try:
                value = self.validate_value(self._runner_path(component_name))
            except ValueError as error:
                return Result(False, message=str(error))

        choice = next(
            (
                item
                for item in self.list_choices(include_unstable=True)
                if item.component_name == component_name and item.value == value
            ),
            None,
        )
        if choice is None:
            choice = UmuProtonChoice(
                key=f"bottles:{component_name}",
                title=component_name,
                value=value,
                source="bottles",
                component_name=component_name,
                installed=True,
                downloadable=True,
            )
        return Result(True, data=choice)

    def component_in_use(self, component_name: str) -> bool:
        try:
            target = Path(self._runner_path(component_name)).resolve()
        except (OSError, RuntimeError):
            return False

        values = [self.manager.settings.get_string("umu-proton")]
        values.extend(game.proton for game in self.manager.umu_repository.list_games())
        for value in values:
            if value == component_name:
                return True
            if (
                value == DEFAULT_PROTON_VALUE
                and component_name == self._latest_protosoda()
            ):
                return True
            if value in AUTO_PROTON_VALUES:
                continue
            try:
                if Path(value).expanduser().resolve() == target:
                    return True
            except (OSError, RuntimeError, TypeError):
                continue
        return False
