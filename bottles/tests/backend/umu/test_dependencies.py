from pathlib import Path
from types import SimpleNamespace

from bottles.backend.globals import Paths
from bottles.backend.models.result import Result
from bottles.backend.umu import UmuDependencyInstaller, UmuGameRepository


class DependencyManager:
    def __init__(self, manifests):
        self.manifests = manifests

    def get_dependency(self, name):
        return self.manifests.get(name)


class ComponentManager:
    def __init__(self, temp):
        self.temp = temp
        self.downloads = []

    def download(self, **kwargs):
        self.downloads.append(kwargs)
        if kwargs.get("func"):
            kwargs["func"](5, 10, None)
        target = self.temp / (kwargs["rename"] or kwargs["file"])
        target.write_bytes(b"installer")
        return Result(True)


class Process:
    def __init__(self, return_code=0):
        self.return_code = return_code

    def wait(self):
        return self.return_code


class Executor:
    def __init__(self, return_codes=None):
        self.games = []
        self.processes = {}
        self.return_codes = iter(return_codes or [])

    def run(self, game):
        self.games.append(game)
        process = Process(next(self.return_codes, 0))
        self.processes[game.id] = process
        return process

    def wait(self, game):
        return self.processes.pop(game.id).wait()


def _installer(tmp_path, monkeypatch, manifests):
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(Paths, "temp", str(temp))
    repository = UmuGameRepository(tmp_path / "umu")
    game_executable = tmp_path / "game.exe"
    game_executable.write_bytes(b"game")
    game = repository.new_game("Game", game_executable, proton="GE-Proton")
    repository.save(game)
    component_manager = ComponentManager(temp)
    manager = SimpleNamespace(
        dependency_manager=DependencyManager(manifests),
        component_manager=component_manager,
    )
    executor = Executor()
    installer = UmuDependencyInstaller(manager, repository, executor)
    return installer, repository, game, component_manager, executor


def test_installs_compatible_bottles_recipe(monkeypatch, tmp_path):
    manifests = {
        "physx": {
            "Dependencies": [],
            "Steps": [
                {
                    "action": "install_exe",
                    "file_name": "PhysX.exe",
                    "rename": "physx.exe",
                    "url": "https://example.com/PhysX.exe",
                    "file_checksum": "abc",
                    "arguments": "/s",
                },
                {
                    "action": "override_dll",
                    "dll": "physxloader",
                    "type": "native,builtin",
                },
            ],
        }
    }
    installer, repository, game, downloads, executor = _installer(
        tmp_path, monkeypatch, manifests
    )

    result = installer.install(game, ["physx"])

    assert result.status is True
    assert len(downloads.downloads) == 1
    assert executor.games[0].arguments == ("/s",)
    assert executor.games[0].executable == Path(Paths.temp) / "physx.exe"
    stored = repository.load(game.id)
    assert stored.extra["installed_dependencies"] == ["physx"]
    assert stored.environment["WINEDLLOVERRIDES"] == "physxloader=native,builtin"


def test_reports_umu_dependency_installation_progress(monkeypatch, tmp_path):
    manifests = {
        "runtime": {
            "Dependencies": [],
            "Steps": [
                {
                    "action": "install_exe",
                    "file_name": "runtime.exe",
                    "url": "https://example.com/runtime.exe",
                },
                {
                    "action": "override_dll",
                    "dll": "runtime",
                    "type": "native,builtin",
                },
            ],
        }
    }
    installer, _repository, game, _downloads, _executor = _installer(
        tmp_path, monkeypatch, manifests
    )
    steps = []
    progress = []

    result = installer.install(
        game,
        ["runtime"],
        progress_cb=steps.append,
        progress_progress_cb=progress.append,
    )

    assert result.status is True
    assert steps == [
        'Installing "runtime"...',
        "Downloading runtime.exe...",
        "Running runtime.exe...",
        "Updating DLL overrides...",
        "Finalizing installation...",
    ]
    assert progress == [0.5, None]


def test_rejects_unsupported_recipe_before_download(monkeypatch, tmp_path):
    manifests = {
        "dotnet": {
            "Dependencies": [],
            "Steps": [{"action": "set_windows", "version": "win7"}],
        }
    }
    installer, _repository, game, downloads, executor = _installer(
        tmp_path, monkeypatch, manifests
    )

    result = installer.install(game, ["dotnet"])

    assert result.status is False
    assert "unsupported UMU action set_windows" in result.message
    assert downloads.downloads == []
    assert executor.games == []


def test_reports_recipe_compatibility_before_install(monkeypatch, tmp_path):
    manifests = {
        "supported": {
            "Dependencies": [],
            "Steps": [
                {
                    "action": "install_exe",
                    "file_name": "setup.exe",
                    "url": "https://example.com/setup.exe",
                }
            ],
        },
        "unsupported": {
            "Dependencies": [],
            "Steps": [{"action": "set_windows", "version": "win7"}],
        },
    }
    installer, _repository, _game, _downloads, _executor = _installer(
        tmp_path, monkeypatch, manifests
    )

    assert installer.is_compatible("supported") is True
    assert installer.is_compatible("unsupported") is False


def test_resolves_recipe_dependencies_once(monkeypatch, tmp_path):
    step = {
        "action": "install_exe",
        "file_name": "setup.exe",
        "url": "https://example.com/setup.exe",
    }
    manifests = {
        "base": {"Dependencies": [], "Steps": [step]},
        "game": {"Dependencies": ["base"], "Steps": [step]},
    }
    installer, repository, game, downloads, _executor = _installer(
        tmp_path, monkeypatch, manifests
    )

    result = installer.install(game, ["game", "base"])

    assert result.status is True
    assert len(downloads.downloads) == 2
    assert repository.load(game.id).extra["installed_dependencies"] == [
        "base",
        "game",
    ]


def test_keeps_completed_dependencies_after_later_failure(monkeypatch, tmp_path):
    def step(name):
        return {
            "action": "install_exe",
            "file_name": f"{name}.exe",
            "url": f"https://example.com/{name}.exe",
        }

    manifests = {
        "first": {"Dependencies": [], "Steps": [step("first")]},
        "second": {"Dependencies": [], "Steps": [step("second")]},
    }
    installer, repository, game, _downloads, _executor = _installer(
        tmp_path, monkeypatch, manifests
    )
    installer.executor = Executor([0, 1])

    result = installer.install(game, ["first", "second"])

    assert result.status is False
    assert result.data.extra["installed_dependencies"] == ["first"]
    assert repository.load(game.id).extra["installed_dependencies"] == ["first"]
