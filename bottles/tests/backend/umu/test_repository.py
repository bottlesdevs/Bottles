from pathlib import Path
from uuid import uuid4

import pytest

from bottles.backend.umu import (
    UmuGame,
    UmuGameRepository,
    UmuPrefix,
    UmuRepositoryError,
    UnsupportedUmuSchemaError,
)
from bottles.backend.utils import yaml


def test_repository_round_trip(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game(
        "Borderlands 3",
        tmp_path / "Borderlands 3.exe",
        proton="GE-Proton10-15",
        game_id="umu-397540",
        store="egs",
        arguments=("-nostartupmovies", "value with spaces"),
        working_directory=tmp_path / "game files",
        environment={"PROTON_ENABLE_NVAPI": "1"},
        sandbox=True,
    )

    path = repository.save(game)
    loaded = repository.load(game.id)

    assert path == repository.config_path(game.id)
    assert loaded == game
    assert loaded.environment == {"PROTON_ENABLE_NVAPI": "1"}
    assert loaded.sandbox is True
    assert loaded.library_id == f"umu:{game.id}"
    assert repository.prefix_path(game) == repository.prefixes_root / str(game.id)
    assert repository.list_games() == [game]


def test_repository_rejects_invalid_sandbox_value(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game(
        "Invalid sandbox",
        "/games/invalid.exe",
        proton="UMU-Proton",
    )
    data = game.to_dict()
    data["sandbox"] = "yes"
    path = repository.config_path(game.id)
    path.parent.mkdir(parents=True)
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")

    with pytest.raises(UmuRepositoryError, match="Cannot load"):
        repository.load(game.id)


def test_repository_preserves_unknown_fields(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game(
        "Unknown fields",
        "/games/example.exe",
        proton="UMU-Proton",
    )
    data = game.to_dict()
    data["future_option"] = {"enabled": True}
    data["prefix"]["future_prefix_option"] = "keep"
    path = repository.config_path(game.id)
    path.parent.mkdir(parents=True)
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")

    loaded = repository.load(game.id)
    repository.save(loaded)
    saved = yaml.load(path.read_text(encoding="utf-8"))

    assert saved["future_option"] == {"enabled": True}
    assert saved["prefix"]["future_prefix_option"] == "keep"


def test_repository_update_preserves_metadata(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Update", "/games/update.exe", proton="UMU-Proton")
    game = UmuGame.from_dict({**game.to_dict(), "future_option": "keep"})
    repository.save(game)

    updated = repository.update(game, state="ready")

    assert updated.state == "ready"
    assert repository.load(game.id).extra == {"future_option": "keep"}


def test_repository_update_keeps_game_id_immutable(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Update", "/games/update.exe", proton="UMU-Proton")

    with pytest.raises(UmuRepositoryError, match="Cannot change"):
        repository.update(game, id=uuid4())


def test_repository_delete_keeps_prefix_by_default(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Delete", "/games/delete.exe", proton="UMU-Proton")
    repository.save(game)
    prefix = repository.prefix_path(game)
    prefix.mkdir(parents=True)
    (prefix / "user-data").write_text("keep", encoding="utf-8")

    assert repository.delete(game) is True
    assert repository.config_path(game.id).exists() is False
    assert (prefix / "user-data").read_text(encoding="utf-8") == "keep"
    assert repository.delete(game) is False


def test_repository_delete_removes_managed_prefix_when_requested(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Delete", "/games/delete.exe", proton="UMU-Proton")
    repository.save(game)
    prefix = repository.prefix_path(game)
    prefix.mkdir(parents=True)
    (prefix / "user-data").touch()

    assert repository.delete(game, delete_prefix=True) is True
    assert prefix.exists() is False
    assert repository.config_path(game.id).exists() is False


def test_repository_does_not_remove_running_game(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Running", "/games/run.exe", proton="UMU-Proton")
    repository.save(game)
    monkeypatch.setattr(
        "bottles.backend.umu.repository.prefix_has_process",
        lambda _prefix: True,
    )

    with pytest.raises(UmuRepositoryError, match="while it is running"):
        repository.delete(game, delete_prefix=True)

    assert repository.config_path(game.id).exists() is True


def test_repository_never_deletes_custom_prefix(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    custom_prefix = tmp_path / "external-prefix"
    custom_prefix.mkdir()
    game = UmuGame(
        id=uuid4(),
        name="Custom",
        executable=Path("/games/custom.exe"),
        prefix=UmuPrefix(str(custom_prefix), managed=False),
        proton="UMU-Proton",
    )
    repository.save(game)

    with pytest.raises(UmuRepositoryError, match="custom"):
        repository.delete(game, delete_prefix=True)

    assert custom_prefix.exists() is True
    assert repository.config_path(game.id).exists() is True


def test_repository_never_deletes_another_games_prefix(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    first = repository.new_game("First", "/games/first.exe", proton="UMU-Proton")
    second = repository.new_game("Second", "/games/second.exe", proton="UMU-Proton")
    repository.save(first)
    repository.save(second)
    second_prefix = repository.prefix_path(second)
    second_prefix.mkdir(parents=True)
    (second_prefix / "user-data").write_text("keep", encoding="utf-8")
    data = first.to_dict()
    data["prefix"]["path"] = f"prefixes/{second.id}"
    path = repository.config_path(first.id)
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
    corrupted = repository.load(first.id)

    with pytest.raises(UmuRepositoryError, match="does not belong"):
        repository.delete(corrupted, delete_prefix=True)

    assert (second_prefix / "user-data").read_text(encoding="utf-8") == "keep"
    assert repository.config_path(first.id).exists() is True


def test_repository_never_follows_prefix_symlink_on_delete(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Symlink", "/games/symlink.exe", proton="UMU-Proton")
    repository.save(game)
    target = repository.prefixes_root / "other-prefix"
    target.mkdir(parents=True)
    (target / "user-data").write_text("keep", encoding="utf-8")
    prefix = repository.prefix_path(game)
    prefix.symlink_to(target, target_is_directory=True)

    with pytest.raises(UmuRepositoryError, match="symbolic link"):
        repository.delete(game, delete_prefix=True)

    assert (target / "user-data").read_text(encoding="utf-8") == "keep"
    assert repository.config_path(game.id).exists() is True


def test_repository_never_writes_through_game_directory_symlink(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Symlink", "/games/symlink.exe", proton="UMU-Proton")
    external = tmp_path / "external"
    external.mkdir()
    game_directory = repository.config_path(game.id).parent
    game_directory.parent.mkdir(parents=True)
    game_directory.symlink_to(external, target_is_directory=True)

    with pytest.raises(UmuRepositoryError, match="symbolic link"):
        repository.save(game)

    assert list(external.iterdir()) == []


def test_repository_does_not_delete_prefix_when_tombstone_fails(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Failure", "/games/failure.exe", proton="UMU-Proton")
    repository.save(game)
    prefix = repository.prefix_path(game)
    prefix.mkdir(parents=True)
    (prefix / "user-data").write_text("keep", encoding="utf-8")

    def fail_replace(_source, _destination):
        raise OSError("failed")

    monkeypatch.setattr("bottles.backend.umu.repository.os.replace", fail_replace)

    with pytest.raises(UmuRepositoryError, match="Cannot delete UMU game"):
        repository.delete(game, delete_prefix=True)

    assert (prefix / "user-data").read_text(encoding="utf-8") == "keep"
    assert repository.config_path(game.id).exists() is True


def test_repository_rejects_future_schema_without_rewriting(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Future", "/games/future.exe", proton="UMU-Proton")
    data = game.to_dict()
    data["schema_version"] = 2
    path = repository.config_path(game.id)
    path.parent.mkdir(parents=True)
    original = yaml.dump(data, sort_keys=False)
    path.write_text(original, encoding="utf-8")

    with pytest.raises(UnsupportedUmuSchemaError):
        repository.load(game.id)

    assert path.read_text(encoding="utf-8") == original


def test_repository_rejects_managed_prefix_outside_root(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = UmuGame(
        id=uuid4(),
        name="Escape",
        executable=Path("/games/escape.exe"),
        prefix=UmuPrefix("../escape"),
        proton="UMU-Proton",
    )

    with pytest.raises(UmuRepositoryError, match="escapes"):
        repository.save(game)


def test_repository_skips_invalid_entries(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Valid", "/games/valid.exe", proton="UMU-Proton")
    repository.save(game)
    invalid = repository.games_root / "not-a-uuid"
    invalid.mkdir(parents=True)
    (invalid / "game.yml").write_text("invalid: true\n", encoding="utf-8")

    assert repository.list_games() == [game]


def test_custom_prefix_must_be_absolute(tmp_path):
    prefix = UmuPrefix("relative/custom", managed=False)

    with pytest.raises(ValueError, match="must be absolute"):
        prefix.resolve(tmp_path)


def test_recover_interrupted_installation(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Setup", "/games/setup.exe", proton="UMU-Proton")
    repository.save(repository.update(game, state="installing"))
    monkeypatch.setattr(
        "bottles.backend.umu.repository.prefix_has_process",
        lambda _prefix: False,
    )

    recovered = repository.recover_interrupted_installations()

    assert [game.state for game in recovered] == ["failed"]
    assert repository.load(game.id).state == "failed"


def test_recovery_keeps_active_installation(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Setup", "/games/setup.exe", proton="UMU-Proton")
    repository.save(repository.update(game, state="installing"))
    monkeypatch.setattr(
        "bottles.backend.umu.repository.prefix_has_process",
        lambda _prefix: True,
    )

    assert repository.recover_interrupted_installations() == []
    assert repository.load(game.id).state == "installing"


def test_game_rejects_unknown_store(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")

    with pytest.raises(ValueError, match="Invalid store"):
        repository.new_game(
            "Game",
            "/games/game.exe",
            proton="UMU-Proton",
            store="unknown",
        )


def test_discovers_standard_umu_prefixes(tmp_path):
    repository = UmuGameRepository(tmp_path / "managed")
    standard = tmp_path / "Games" / "umu"
    prefix = standard / "umu-1234"
    prefix.joinpath("pfx", "drive_c").mkdir(parents=True)
    standard.joinpath("empty").mkdir()

    assert repository.discover_standard_prefixes(standard) == [prefix]


def test_discovery_excludes_configured_prefix(tmp_path):
    repository = UmuGameRepository(tmp_path / "managed")
    standard = tmp_path / "Games" / "umu"
    prefix = standard / "umu-1234"
    prefix.joinpath("pfx", "drive_c").mkdir(parents=True)
    game = repository.new_game(
        "Game",
        "/games/game.exe",
        proton="UMU-Proton",
    )
    game = repository.update(game, prefix=UmuPrefix(str(prefix), managed=False))

    assert repository.discover_standard_prefixes(standard) == []
