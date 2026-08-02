from pathlib import Path
from types import SimpleNamespace

import pytest
from gi.repository import Gio

resource_path = Path("/app/share/bottles/bottles.gresource")
if not resource_path.is_file():
    pytest.skip(
        "Dependency frontend tests require the Bottles Flatpak runtime",
        allow_module_level=True,
    )

Gio.resources_register(Gio.Resource.load(str(resource_path)))

from bottles.backend.models.config import BottleConfig  # noqa: E402
from bottles.backend.models.result import Result  # noqa: E402
from bottles.frontend.views import bottle_dependencies  # noqa: E402
from bottles.frontend.views.bottle_dependencies import DependenciesView  # noqa: E402
from bottles.frontend.widgets.dependency import DependencyEntry  # noqa: E402


class DialogStub:
    instances = []

    def __init__(self, *_args):
        self.steps = []
        self.progress = []
        self.finished = None
        self.instances.append(self)

    def add_step(self, step):
        self.steps.append(step)

    def update_progress(self, progress):
        self.progress.append(progress)

    def present(self):
        pass

    def finish(self, success, message):
        self.finished = (success, message)


def _entry(name):
    return SimpleNamespace(dependency=(name, {}))


class WidgetStub:
    def __init__(self, visible=False, active=True):
        self.visible = visible
        self.active = active
        self.sensitive = True
        self.label = ""

    def get_visible(self):
        return self.visible

    def set_visible(self, visible):
        self.visible = visible

    def set_active(self, active):
        self.active = active

    def get_active(self):
        return self.active

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive

    def get_sensitive(self):
        return self.sensitive

    def set_label(self, label):
        self.label = label

    def stop(self):
        pass


def test_batch_skips_dependency_installed_as_a_prerequisite():
    config = BottleConfig(Name="Test")
    calls = []

    def install(config, dependency, **_kwargs):
        calls.append(dependency[0])
        config.Installed_Dependencies.extend(["first", "second"])
        return Result(True)

    view = SimpleNamespace(
        config=config,
        manager=SimpleNamespace(
            dependency_manager=SimpleNamespace(install=install),
        ),
    )

    result = DependenciesView._DependenciesView__install_dependencies(
        view, [_entry("first"), _entry("second")], DialogStub()
    )

    assert result.ok
    assert result.data == {"installed": ["first", "second"], "failed": []}
    assert calls == ["first"]


def test_batch_continues_after_a_dependency_fails():
    config = BottleConfig(Name="Test")
    calls = []

    def install(config, dependency, **_kwargs):
        name = dependency[0]
        calls.append(name)
        if name == "broken":
            return Result(False)
        config.Installed_Dependencies.append(name)
        return Result(True)

    view = SimpleNamespace(
        config=config,
        manager=SimpleNamespace(
            dependency_manager=SimpleNamespace(install=install),
        ),
    )

    result = DependenciesView._DependenciesView__install_dependencies(
        view, [_entry("broken"), _entry("working")], DialogStub()
    )

    assert not result.ok
    assert result.data == {"installed": ["working"], "failed": ["broken"]}
    assert calls == ["broken", "working"]


def test_batch_continues_after_an_installation_raises():
    config = BottleConfig(Name="Test")
    calls = []

    def install(config, dependency, **_kwargs):
        name = dependency[0]
        calls.append(name)
        if name == "broken":
            raise RuntimeError("failed")
        config.Installed_Dependencies.append(name)
        return Result(True)

    view = SimpleNamespace(
        config=config,
        manager=SimpleNamespace(
            dependency_manager=SimpleNamespace(install=install),
        ),
    )

    result = DependenciesView._DependenciesView__install_dependencies(
        view, [_entry("broken"), _entry("working")], DialogStub()
    )

    assert not result.ok
    assert result.data == {"installed": ["working"], "failed": ["broken"]}
    assert calls == ["broken", "working"]


def test_batch_refreshes_automatic_versioning(monkeypatch):
    config = BottleConfig(Name="Test")
    config.Parameters.versioning_automatic = True
    versioning_updates = []
    view_updates = []

    def install(config, dependency, **_kwargs):
        config.Installed_Dependencies.append(dependency[0])
        return Result(True)

    def run_async(task_func, callback, **kwargs):
        callback(task_func(**kwargs), False)

    monkeypatch.setattr(bottle_dependencies, "DependencyInstallDialog", DialogStub)
    monkeypatch.setattr(bottle_dependencies, "RunAsync", run_async)

    view = SimpleNamespace(
        config=config,
        manager=SimpleNamespace(
            dependency_manager=SimpleNamespace(install=install),
        ),
        window=SimpleNamespace(
            page_details=SimpleNamespace(
                view_versioning=SimpleNamespace(
                    update=lambda: versioning_updates.append(True)
                )
            ),
            show_toast=lambda _message: None,
        ),
        queue=SimpleNamespace(add_task=lambda: None, end_task=lambda: None),
        list_dependencies=WidgetStub(),
        btn_select_all=WidgetStub(),
        btn_install_selected=WidgetStub(),
        _DependenciesView__registry=[
            SimpleNamespace(
                dependency=("working", {}),
                check_select=WidgetStub(visible=True, active=True),
            )
        ],
        update=lambda config: view_updates.append(config),
    )
    view._DependenciesView__install_dependencies = lambda entries, dialog: (
        DependenciesView._DependenciesView__install_dependencies(view, entries, dialog)
    )

    DependenciesView._DependenciesView__install_selected(view)

    assert versioning_updates == [True]
    assert view_updates == [config]
    assert DialogStub.instances[-1].finished == (True, "1 dependency installed.")


def test_installed_dependency_is_removed_from_batch_selection():
    check_select = WidgetStub(visible=True)
    entry = SimpleNamespace(
        btn_install=WidgetStub(visible=True),
        btn_remove=WidgetStub(),
        btn_reinstall=WidgetStub(),
        check_select=check_select,
        spinner=WidgetStub(),
        get_parent=lambda: None,
    )

    DependencyEntry.set_installed(entry)

    assert not check_select.visible
    assert not check_select.active


def test_select_all_toggles_only_installable_dependencies():
    first = WidgetStub(visible=True, active=False)
    second = WidgetStub(visible=True, active=False)
    unavailable = WidgetStub(visible=False, active=False)
    view = SimpleNamespace(
        _DependenciesView__registry=[
            SimpleNamespace(check_select=first),
            SimpleNamespace(check_select=second),
            SimpleNamespace(check_select=unavailable),
        ]
    )

    DependenciesView._DependenciesView__toggle_all(view)

    assert first.active
    assert second.active
    assert not unavailable.active

    DependenciesView._DependenciesView__toggle_all(view)

    assert not first.active
    assert not second.active
    assert not unavailable.active


def test_selection_controls_reflect_complete_selection():
    first = WidgetStub(visible=True, active=True)
    second = WidgetStub(visible=True, active=False)
    select_all = WidgetStub()
    install_selected = WidgetStub()
    view = SimpleNamespace(
        _DependenciesView__registry=[
            SimpleNamespace(check_select=first),
            SimpleNamespace(check_select=second),
        ],
        list_dependencies=WidgetStub(),
        btn_select_all=select_all,
        btn_install_selected=install_selected,
    )

    DependenciesView._DependenciesView__selection_changed(view)

    assert select_all.visible
    assert select_all.sensitive
    assert select_all.label == "Select All"
    assert install_selected.visible
    assert install_selected.sensitive

    second.set_active(True)
    DependenciesView._DependenciesView__selection_changed(view)

    assert select_all.label == "Clear Selection"

    view.list_dependencies.set_sensitive(False)
    DependenciesView._DependenciesView__selection_changed(view)

    assert not select_all.sensitive
    assert not install_selected.sensitive
