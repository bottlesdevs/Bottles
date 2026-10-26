from datetime import datetime, timedelta

from bottles.backend.managers.journal import JournalManager, JournalSeverity
from bottles.backend.utils import yaml


def test_bad_timestamp_does_not_block_writes_or_discard_other_events(tmp_path, monkeypatch):
    path = tmp_path / "journal.yml"
    monkeypatch.setattr(JournalManager, "path", str(path))
    now = datetime.now()
    events = {
        "broken": {"timestamp": "202-14 11:14:42", "message": "Keep this report"},
        "recent": {"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), "message": "Recent"},
        "old": {"timestamp": (now - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S"), "message": "Expired"},
    }
    with path.open("w") as stream:
        yaml.dump(events, stream)

    JournalManager.write(JournalSeverity.WARNING, "A new warning")

    all_events = JournalManager.get("all")
    assert all_events["broken"] == events["broken"]
    assert all_events["recent"] == events["recent"]
    assert "old" not in all_events
    assert any(event["message"] == "A new warning" for event in all_events.values())
    assert "broken" not in JournalManager.get("today")

