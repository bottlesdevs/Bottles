import contextlib
import os
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.umu.models import (
    UmuGame,
    UmuModelError,
    UmuPrefix,
    UnsupportedUmuSchemaError,
)
from bottles.backend.umu.processes import prefix_has_process
from bottles.backend.utils import yaml

logging = Logger()


class UmuRepositoryError(RuntimeError):
    pass


class UmuGameRepository:
    def __init__(self, root: str | Path | None = None):
        self.root = (
            (Path(root) if root is not None else Path(Paths.base).joinpath("umu"))
            .expanduser()
            .resolve(strict=False)
        )
        self.games_root = self.root.joinpath("games")
        self.prefixes_root = self.root.joinpath("prefixes")

    @staticmethod
    def _game_id(value: UUID | str) -> UUID:
        try:
            return value if isinstance(value, UUID) else UUID(str(value))
        except (TypeError, ValueError, AttributeError) as error:
            raise UmuRepositoryError("Invalid UMU game id") from error

    def config_path(self, game_id: UUID | str) -> Path:
        game_uuid = self._game_id(game_id)
        return self.games_root.joinpath(str(game_uuid), "game.yml")

    def prefix_path(self, game: UmuGame) -> Path:
        if not isinstance(game, UmuGame):
            raise UmuRepositoryError("Invalid UMU game")
        return game.prefix.resolve(self.root)

    def new_game(
        self,
        name: str,
        executable: str | Path,
        *,
        proton: str,
        game_id: str = "umu-default",
        store: str = "none",
        arguments: tuple[str, ...] | list[str] = (),
        working_directory: str | Path | None = None,
        environment: dict[str, str] | None = None,
        sandbox: bool = False,
        share_net: bool = False,
    ) -> UmuGame:
        item_id = uuid4()
        prefix = UmuPrefix(path=f"prefixes/{item_id}")
        return UmuGame(
            id=item_id,
            name=name,
            executable=Path(executable),
            prefix=prefix,
            proton=proton,
            game_id=game_id,
            store=store,
            arguments=tuple(arguments),
            working_directory=(
                Path(working_directory) if working_directory is not None else None
            ),
            environment=environment or {},
            sandbox=sandbox,
            share_net=share_net,
        )

    def _prepare_game_directory(self, game: UmuGame) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or self.games_root.is_symlink():
            raise UmuRepositoryError("Cannot save through a symbolic link")
        self.games_root.mkdir(exist_ok=True)
        game_directory = self.config_path(game.id).parent
        if game_directory.is_symlink():
            raise UmuRepositoryError("Cannot save through a symbolic link")
        game_directory.mkdir(exist_ok=True)
        return game_directory

    def save(self, game: UmuGame) -> Path:
        if not isinstance(game, UmuGame):
            raise UmuRepositoryError("Invalid UMU game")
        try:
            prefix = self.prefix_path(game)
        except UmuModelError as error:
            raise UmuRepositoryError(str(error)) from error
        if game.prefix.managed and prefix != self.prefixes_root.joinpath(str(game.id)):
            raise UmuRepositoryError("Managed prefix does not belong to the UMU game")

        path = self.config_path(game.id)
        self._prepare_game_directory(game)
        file_descriptor = -1
        temporary = None
        try:
            file_descriptor, temporary = tempfile.mkstemp(
                dir=path.parent, prefix=".game-", suffix=".tmp"
            )
            with os.fdopen(file_descriptor, mode="w", encoding="utf-8") as stream:
                file_descriptor = -1
                yaml.dump(game.to_dict(), stream, sort_keys=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
        except (OSError, yaml.YAMLError) as error:
            raise UmuRepositoryError(f"Cannot save UMU game {game.id}") from error
        finally:
            if file_descriptor >= 0:
                os.close(file_descriptor)
            if temporary is not None:
                with contextlib.suppress(OSError):
                    os.remove(temporary)
        return path

    def update(self, game: UmuGame, **changes: Any) -> UmuGame:
        if not isinstance(game, UmuGame):
            raise UmuRepositoryError("Invalid UMU game")
        if "id" in changes and changes["id"] != game.id:
            raise UmuRepositoryError("Cannot change a UMU game id")
        try:
            updated = replace(game, **changes)
        except (TypeError, UmuModelError) as error:
            raise UmuRepositoryError("Invalid UMU game update") from error
        self.save(updated)
        return updated

    def recover_interrupted_installations(self) -> list[UmuGame]:
        recovered = []
        for game in self.list_games():
            if game.state != "installing":
                continue
            if prefix_has_process(self.prefix_path(game)):
                continue
            recovered.append(self.update(game, state="failed"))
        return recovered

    def delete(self, game: UmuGame, *, delete_prefix: bool = False) -> bool:
        if not isinstance(game, UmuGame):
            raise UmuRepositoryError("Invalid UMU game")
        try:
            stored = self.load(game.id)
        except FileNotFoundError:
            return False

        try:
            stored_prefix = self.prefix_path(stored)
        except UmuModelError as error:
            raise UmuRepositoryError(str(error)) from error
        if prefix_has_process(stored_prefix):
            raise UmuRepositoryError("Cannot remove a UMU game while it is running")

        prefix = None
        if delete_prefix:
            if not stored.prefix.managed:
                raise UmuRepositoryError("Cannot delete a custom UMU prefix")
            try:
                prefix = Path(os.path.abspath(self.root.joinpath(stored.prefix.path)))
                prefix.relative_to(self.prefixes_root)
            except (UmuModelError, ValueError) as error:
                raise UmuRepositoryError(
                    "Managed prefix is outside the UMU prefixes directory"
                ) from error
            if prefix == self.prefixes_root:
                raise UmuRepositoryError("Cannot delete the UMU prefixes directory")
            if prefix != self.prefixes_root.joinpath(str(stored.id)):
                raise UmuRepositoryError(
                    "Managed prefix does not belong to the UMU game"
                )
            if self.root.is_symlink() or self.prefixes_root.is_symlink():
                raise UmuRepositoryError("Cannot delete through a symbolic link")
            current = self.prefixes_root
            for part in prefix.relative_to(self.prefixes_root).parts:
                current = current.joinpath(part)
                if current.is_symlink():
                    raise UmuRepositoryError("Cannot delete a symbolic link prefix")

        game_directory = self.config_path(stored.id).parent
        if (
            self.root.is_symlink()
            or self.games_root.is_symlink()
            or game_directory.is_symlink()
        ):
            raise UmuRepositoryError("Cannot delete a symbolic link game directory")
        tombstone = self.games_root.joinpath(f".deleted-{uuid4()}")
        try:
            os.replace(game_directory, tombstone)
        except OSError as error:
            raise UmuRepositoryError(f"Cannot delete UMU game {stored.id}") from error

        if prefix is not None and prefix.exists():
            try:
                shutil.rmtree(prefix)
            except OSError as error:
                try:
                    os.replace(tombstone, game_directory)
                except OSError as rollback_error:
                    raise UmuRepositoryError(
                        f"Cannot restore UMU game {stored.id} after delete failure"
                    ) from rollback_error
                raise UmuRepositoryError(
                    f"Cannot delete UMU prefix {prefix}"
                ) from error

        try:
            shutil.rmtree(tombstone)
        except OSError:
            logging.warning(f"Cannot clean deleted UMU game metadata at {tombstone}.")
        return True

    def load(self, game_id: UUID | str) -> UmuGame:
        expected_id = self._game_id(game_id)
        path = self.config_path(expected_id)
        try:
            with path.open(mode="r", encoding="utf-8") as stream:
                data = yaml.load(stream)
            game = UmuGame.from_dict(data)
        except FileNotFoundError:
            raise
        except UnsupportedUmuSchemaError:
            raise
        except (OSError, yaml.YAMLError, UmuModelError) as error:
            raise UmuRepositoryError(f"Cannot load UMU game {expected_id}") from error

        if game.id != expected_id:
            raise UmuRepositoryError(
                f"UMU game id does not match its directory: {expected_id}"
            )
        return game

    def list_games(self) -> list[UmuGame]:
        if not self.games_root.is_dir():
            return []

        games = []
        for path in sorted(self.games_root.iterdir(), key=lambda item: item.name):
            if not path.is_dir():
                continue
            try:
                games.append(self.load(path.name))
            except (
                FileNotFoundError,
                UnsupportedUmuSchemaError,
                UmuRepositoryError,
            ):
                logging.warning(f"Skipping invalid UMU game at {path}.")
        return games

    def discover_standard_prefixes(self, root: str | Path | None = None) -> list[Path]:
        standard_root = (
            Path(root) if root is not None else Path.home().joinpath("Games", "umu")
        ).expanduser()
        if not standard_root.is_dir():
            return []

        configured = {
            self.prefix_path(game).resolve(strict=False) for game in self.list_games()
        }
        discovered = []
        for path in sorted(
            standard_root.iterdir(), key=lambda item: item.name.casefold()
        ):
            if path.name.startswith(".") or not path.is_dir():
                continue
            resolved = path.resolve(strict=False)
            if resolved in configured:
                continue
            proton_prefix = resolved.joinpath("pfx")
            if not proton_prefix.joinpath("drive_c").is_dir():
                continue
            discovered.append(resolved)
        return discovered
