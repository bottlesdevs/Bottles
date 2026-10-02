import pytest

from bottles.backend.utils.display import DisplayUtils


@pytest.mark.parametrize(
    "session_type,wayland_display,expected",
    [
        (None, "wayland-0", "wayland"),
        ("", "wayland-0", "wayland"),
        (None, None, "x11"),
        (None, "", "x11"),
        ("X11", "wayland-0", "x11"),
        ("WAYLAND", None, "wayland"),
    ],
)
def test_display_server_type(monkeypatch, session_type, wayland_display, expected):
    for name, value in (
        ("XDG_SESSION_TYPE", session_type),
        ("WAYLAND_DISPLAY", wayland_display),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    assert DisplayUtils.display_server_type() == expected
