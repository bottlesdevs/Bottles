from types import SimpleNamespace

from bottles.backend.managers.component import ComponentManager


def test_external_runner_cannot_be_uninstalled(tmp_path):
    runner = tmp_path / "GE-Proton10-4"
    runner.mkdir()
    manager = SimpleNamespace(
        external_runners={runner.name},
        local_bottles={},
    )
    component_manager = object.__new__(ComponentManager)
    component_manager._ComponentManager__manager = manager

    result = component_manager.uninstall("runner:proton", runner.name)

    assert not result.ok
    assert result.data == {
        "message": "External runners cannot be removed from Bottles."
    }
    assert runner.is_dir()
