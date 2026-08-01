from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from multiprocessing import get_context
from pathlib import Path
from types import SimpleNamespace

import pytest


class TemplateStub:
    def __init__(self, **_kwargs):
        pass

    def __call__(self, cls):
        return cls

    @staticmethod
    def Child():
        return None


class FakeWidget:
    def __init__(self):
        self.visible = None
        self.label = None
        self.sensitive = None
        self.fraction = None

    def set_visible(self, value):
        self.visible = value

    def set_label(self, value):
        self.label = value

    def set_sensitive(self, value):
        self.sensitive = value

    def set_fraction(self, value):
        self.fraction = value


class FakeCarousel:
    def set_allow_long_swipes(self, _value):
        pass

    def set_allow_mouse_drag(self, _value):
        pass

    def set_allow_scroll_wheel(self, _value):
        pass


def probe_failed_setup(queue, raises_error):
    import gi

    from bottles.backend.models.result import Result

    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    Gtk = import_module("gi.repository.Gtk")

    spec = spec_from_file_location(
        "_test_onboard_module",
        Path(__file__).parents[2] / "frontend" / "windows" / "onboard.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the onboard module")
    onboard_module = module_from_spec(spec)

    template = Gtk.Template
    Gtk.Template = TemplateStub
    try:
        spec.loader.exec_module(onboard_module)
    finally:
        Gtk.Template = template

    callback = {}

    def run_async(*_args, **kwargs):
        callback["finished"] = kwargs["callback"]

    onboard_module.RunAsync = run_async
    onboard_module.GtkUtils.run_in_main_loop = staticmethod(lambda func: func)

    dialog = SimpleNamespace(
        manager=SimpleNamespace(checks=lambda: None),
        btn_back=FakeWidget(),
        btn_next=FakeWidget(),
        btn_install=FakeWidget(),
        btn_cancel=FakeWidget(),
        btn_close=FakeWidget(),
        progressbar=FakeWidget(),
        label_progress=FakeWidget(),
        label_status=FakeWidget(),
        label_skip=FakeWidget(),
        carousel=FakeCarousel(),
        set_can_close=lambda value: setattr(dialog, "can_close", value),
        _OnboardDialog__handle_progress=lambda **_kwargs: None,
    )

    onboard_module.OnboardDialog._OnboardDialog__install_runner(dialog, None)
    result = None if raises_error else Result(False)
    error = RuntimeError("network failure") if raises_error else None
    callback["finished"](result, error)

    failed = {
        "can_close": dialog.can_close,
        "back_visible": dialog.btn_back.visible,
        "retry_visible": dialog.btn_install.visible,
        "retry_label": dialog.btn_install.label,
        "skip_visible": dialog.btn_cancel.visible,
        "progress_visible": dialog.progressbar.visible,
        "progress_label_visible": dialog.label_progress.visible,
        "status": dialog.label_status.label,
    }

    onboard_module.OnboardDialog._OnboardDialog__install_runner(dialog, None)
    retrying = {
        "can_close": dialog.can_close,
        "skip_visible": dialog.btn_cancel.visible,
        "progress_visible": dialog.progressbar.visible,
        "status_visible": dialog.label_status.visible,
    }
    queue.put((failed, retrying))


@pytest.mark.parametrize("raises_error", (False, True))
def test_failed_setup_can_retry_or_skip_setup(raises_error):
    context = get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=probe_failed_setup, args=(queue, raises_error))
    process.start()
    process.join(10)

    if process.is_alive():
        process.terminate()
        process.join()
        pytest.fail("Onboarding state probe timed out")

    assert process.exitcode == 0
    failed, retrying = queue.get(timeout=1)

    assert failed == {
        "can_close": True,
        "back_visible": True,
        "retry_visible": True,
        "retry_label": "Try Again",
        "skip_visible": True,
        "progress_visible": False,
        "progress_label_visible": False,
        "status": (
            "Setup could not be completed. Check your connection and try again, "
            "or skip setup for now."
        ),
    }
    assert retrying == {
        "can_close": False,
        "skip_visible": False,
        "progress_visible": True,
        "status_visible": False,
    }
