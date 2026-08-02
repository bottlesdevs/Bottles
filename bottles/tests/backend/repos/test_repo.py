from types import SimpleNamespace

import pytest

from bottles.backend.managers.component import ComponentManager
from bottles.backend.managers.dependency import DependencyManager
from bottles.backend.managers.installer import InstallerManager
from bottles.backend.repos import repo as repo_module
from bottles.backend.repos.component import ComponentRepo


@pytest.mark.parametrize("callback_in_main_loop", [True, False])
def test_catalog_callback_mode_is_configurable(monkeypatch, callback_in_main_loop):
    callback_modes = []

    class ImmediateRunAsync:
        def __init__(
            self,
            task_func,
            callback=None,
            callback_in_main_loop=True,
            **kwargs,
        ):
            callback_modes.append(callback_in_main_loop)
            callback(task_func(**kwargs), None)

    monkeypatch.setattr(repo_module, "RunAsync", ImmediateRunAsync)

    repository = ComponentRepo(
        "file:///missing",
        "",
        offline=True,
        callback_in_main_loop=callback_in_main_loop,
    )

    assert repository.catalog == {}
    assert callback_modes == [callback_in_main_loop]


@pytest.mark.parametrize(
    ("manager_type", "repository_name"),
    [
        (ComponentManager, "components"),
        (DependencyManager, "dependencies"),
        (InstallerManager, "installers"),
    ],
)
@pytest.mark.parametrize(
    ("is_cli", "callback_in_main_loop"), [(True, False), (False, True)]
)
def test_repository_callbacks_leave_the_main_loop_only_for_cli(
    manager_type,
    repository_name,
    is_cli,
    callback_in_main_loop,
):
    calls = []
    repository_manager = SimpleNamespace(
        get_repo=lambda *args, **kwargs: calls.append((args, kwargs)) or object()
    )
    manager = SimpleNamespace(
        repository_manager=repository_manager,
        is_cli=is_cli,
        utils_conn=object(),
        component_manager=object(),
    )

    manager_type(manager)

    assert calls == [
        (
            (repository_name, False),
            {"callback_in_main_loop": callback_in_main_loop},
        )
    ]
