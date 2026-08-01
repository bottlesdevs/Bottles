import os
from pathlib import Path

from bottles.frontend.utils.localization import (
    UI_LANGUAGES,
    apply_ui_language,
    get_ui_language_environment,
)


def test_ui_languages_match_shipped_catalogs():
    linguas = (
        (Path(__file__).resolve().parents[3] / "po" / "LINGUAS")
        .read_text()
        .splitlines()
    )
    codes = [code for code, _name in UI_LANGUAGES]

    assert codes[:2] == ["system", "en"]
    assert set(codes[2:]) == set(linguas)
    assert len(codes) == len(set(codes))


def test_ui_language_overrides_messages(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "ja")

    apply_ui_language("en")

    assert os.environ["LANGUAGE"] == "en"


def test_system_ui_language_keeps_environment(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "ja")

    apply_ui_language("system")

    assert os.environ["LANGUAGE"] == "ja"


def test_unknown_ui_language_keeps_environment(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "de")

    apply_ui_language("not-a-language")

    assert os.environ["LANGUAGE"] == "de"


def test_relaunch_restores_inherited_language(monkeypatch):
    monkeypatch.setattr("bottles.frontend.utils.localization._INHERITED_LANGUAGE", "ja")
    monkeypatch.setenv("LANGUAGE", "en")

    environment = get_ui_language_environment("system")

    assert environment["LANGUAGE"] == "ja"
    assert os.environ["LANGUAGE"] == "en"


def test_relaunch_removes_application_override(monkeypatch):
    monkeypatch.setattr("bottles.frontend.utils.localization._INHERITED_LANGUAGE", None)
    monkeypatch.setenv("LANGUAGE", "en")

    environment = get_ui_language_environment("system")

    assert "LANGUAGE" not in environment
    assert os.environ["LANGUAGE"] == "en"


def test_relaunch_uses_selected_language(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "ja")

    environment = get_ui_language_environment("en")

    assert environment["LANGUAGE"] == "en"
    assert os.environ["LANGUAGE"] == "ja"


def test_relaunch_keeps_unknown_language(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "de")

    environment = get_ui_language_environment("not-a-language")

    assert environment["LANGUAGE"] == "de"
    assert os.environ["LANGUAGE"] == "de"


def test_relaunch_does_not_restore_gtk_theme(monkeypatch):
    monkeypatch.setenv("GTK_THEME", "broken-theme")

    environment = get_ui_language_environment("system")

    assert "GTK_THEME" not in environment
    assert os.environ["GTK_THEME"] == "broken-theme"
