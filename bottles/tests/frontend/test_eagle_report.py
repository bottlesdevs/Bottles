# ruff: noqa: E402

import os
from pathlib import Path
from types import SimpleNamespace

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
from gi.repository import Gio

resource_path = Path(
    os.environ.get("BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource")
)
if not resource_path.exists():
    pytest.skip(
        "Eagle report tests require the Bottles resource bundle",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))

from bottles.frontend.views import eagle


@pytest.fixture
def report(monkeypatch):
    dialogs = []

    def dialog(**kwargs):
        dialogs.append(kwargs)
        return SimpleNamespace(present=lambda: None)

    monkeypatch.setattr(eagle, "SourceDialog", dialog)

    def generate(data, selected=()):
        rows = []
        for active in selected:
            rows.append(SimpleNamespace(get_active=lambda active=active: active))
        for index, row in enumerate(rows):
            sibling = rows[index + 1] if index + 1 < len(rows) else None
            row.get_next_sibling = lambda sibling=sibling: sibling
        panel = SimpleNamespace(
            analysis_results=data,
            details=SimpleNamespace(window=object()),
            list_suggestions=SimpleNamespace(
                get_first_child=lambda: rows[0] if rows else None
            ),
        )
        eagle.EagleView._EagleView__on_report_clicked(panel, None)
        assert len(dialogs) == 1
        assert dialogs[0]["lang"] == "markdown"
        return dialogs[0]["message"]

    return generate


def test_report_uses_current_selection_for_duplicate_keys(report):
    text = report(
        {"suggestions": [
            {"key": "dxvk_nvapi", "label": "First NVAPI", "value": True},
            {"key": "dep_vcredist", "label": "Visual C++"},
            {"key": "dxvk_nvapi", "label": "Second NVAPI", "value": False},
        ]},
        selected=[False, True],
    )

    assert "- [ ] First NVAPI" in text
    assert "- [x] Second NVAPI" in text
    assert "## Recommended Dependencies\n" in text
    assert "- Visual C++" in text


def test_report_includes_analysis_messages_and_alerts(report):
    text = report({
        "messages": [{"name": "WPF", "description": "Requires .NET"}],
        "details": {
            "Warning": [{"name": "Packed", "severity": "high"}],
            "Security": [{"name": "Pattern fixture", "source": "Fixture rule"}],
            "System": [{"name": "Driver fixture", "severity": "critical"}],
        },
    })

    assert "### [INFO] WPF\nRequires .NET" in text
    assert "### [HIGH] Packed" in text
    assert "### [INFO] Pattern fixture\n*Source: Fixture rule*" in text
    assert "### [CRITICAL] Driver fixture" in text


@pytest.mark.parametrize("category", ["Upscaling", "Physics", "Media", "Crypto", "System"])
def test_report_keeps_detected_technology_categories(report, category):
    text = report({"details": {category: [{"name": "Fixture", "source": "Import"}]}})

    assert f"### {category}\n- **Fixture**  \n  *Source: Import*" in text


def test_report_preserves_metadata_and_empty_intel(report):
    text = report({
        "name": "Fixture.exe",
        "metadata": {"compiler": "Fixture compiler", "dep_enabled": True},
        "intel": None,
        "details": {"Analysed Files": ["Fixture.exe"]},
    })

    assert "**Target:** `Fixture.exe`" in text
    assert "- **Compiler:** Fixture compiler" in text
    assert "- **PE Flags:** DEP" in text
    assert "- `Fixture.exe`" in text
    assert "## Community Intelligence" not in text


@pytest.mark.parametrize("source", ["winetricks", "protondb"])
def test_report_keeps_available_community_evidence(report, source):
    intel = {
        "name": "Fixture", "source": source, "match": "name",
        "notes": ["Fixture note"],
        "attributions": [{
            "name": "Fixture data", "url": "https://example.org/data",
            "licenses": [{"name": "Fixture license", "url": "https://example.org/license"}],
        }],
    }
    if source == "protondb":
        intel.update(tier="gold", reports=4, verdict_yes=3, verdict_no=1)
    text = report({"intel": intel})

    assert f"- **Source:** {source}" in text
    assert "- **Match:** name" in text
    assert "- **Note:** Fixture note" in text
    assert "- **Data credit:** [Fixture data](https://example.org/data)" in text
    assert "[Fixture license](https://example.org/license)" in text
    if source == "protondb":
        assert "- **Reports:** 4\n- **Verdict:** 3 positive / 1 negative" in text
        assert "not an official ProtonDB rating" in text
    else:
        assert "**Reports:**" not in text
        assert "**Verdict:**" not in text
