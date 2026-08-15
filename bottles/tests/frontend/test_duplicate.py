from types import SimpleNamespace

import pytest
from gi.repository import Gio

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.backend.models.result import Result  # noqa: E402
from bottles.frontend.windows.duplicate import DuplicateDialog  # noqa: E402


class EntryStub:
    def __init__(self, text):
        self.text = text
        self.css_classes = set()

    def get_text(self):
        return self.text

    def add_css_class(self, css_class):
        self.css_classes.add(css_class)

    def remove_css_class(self, css_class):
        self.css_classes.discard(css_class)


@pytest.mark.parametrize(
    ("name", "existing_names", "expected_sensitive"),
    (
        ("", {}, False),
        ("   ", {}, False),
        ("Existing", {"Existing": object()}, False),
        ("New Bottle", {}, True),
    ),
)
def test_duplicate_name_validation(name, existing_names, expected_sensitive):
    dialog = SimpleNamespace(
        entry_name=EntryStub(name),
        btn_duplicate=SimpleNamespace(
            set_sensitive=lambda value: setattr(dialog, "sensitive", value)
        ),
        parent=SimpleNamespace(manager=SimpleNamespace(local_bottles=existing_names)),
    )

    DuplicateDialog._DuplicateDialog__check_entry_name(dialog)

    assert dialog.sensitive is expected_sensitive
    assert ("error" in dialog.entry_name.css_classes) is not expected_sensitive


def _make_finish_dialog():
    dialog = SimpleNamespace(
        pulse_id=None,
        parent=SimpleNamespace(
            manager=SimpleNamespace(
                update_bottles=lambda: setattr(dialog, "updated", True)
            )
        ),
        page_failed=SimpleNamespace(
            set_description=lambda value: setattr(dialog, "failure_message", value)
        ),
        stack_switcher=SimpleNamespace(
            set_visible_child_name=lambda value: setattr(dialog, "page", value)
        ),
        updated=False,
        failure_message=None,
        page=None,
    )
    return dialog


def test_duplicate_finish_shows_success_and_refreshes_bottles():
    dialog = _make_finish_dialog()

    DuplicateDialog.finish.__wrapped__(dialog, Result(status=True))

    assert dialog.updated
    assert dialog.page == "page_duplicated"
    assert dialog.failure_message is None


@pytest.mark.parametrize(
    ("result", "error", "expected_message"),
    (
        (Result(status=False, message="copy failed"), None, "copy failed"),
        (None, RuntimeError("disk full"), "disk full"),
    ),
)
def test_duplicate_finish_shows_failure_without_refreshing_bottles(
    result, error, expected_message
):
    dialog = _make_finish_dialog()

    DuplicateDialog.finish.__wrapped__(dialog, result, error)

    assert not dialog.updated
    assert dialog.page == "page_failed"
    assert dialog.failure_message == expected_message
