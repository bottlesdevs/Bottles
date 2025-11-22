"""Unit tests for playtime frontend service."""

import tempfile
from datetime import datetime, timedelta

from bottles.backend.managers.playtime import ProcessSessionTracker
from bottles.frontend.utils.playtime import PlaytimeService


class MockManager:
    """Mock manager for testing."""

    def __init__(self, tracker):
        self.playtime_tracker = tracker


def test_format_playtime():
    """Test playtime formatting rules."""
    assert PlaytimeService.format_playtime(30) == "<1m"
    assert PlaytimeService.format_playtime(60) == "1m"
    assert PlaytimeService.format_playtime(150) == "2m"
    assert PlaytimeService.format_playtime(3599) == "59m"
    assert PlaytimeService.format_playtime(3600) == "1h 00m"
    assert PlaytimeService.format_playtime(3660) == "1h 01m"
    assert PlaytimeService.format_playtime(7325) == "2h 02m"
    assert PlaytimeService.format_playtime(86400) == "1d 00h"
    assert PlaytimeService.format_playtime(90000) == "1d 01h"
    assert PlaytimeService.format_playtime(180000) == "2d 02h"


def test_format_last_played():
    """Test last played date formatting with i18n support."""
    now = datetime.now()

    # These now return translated strings, but we can still test the logic
    result_none = PlaytimeService.format_last_played(None)
    assert "never" in result_none.lower() or result_none == "Never"
    
    result_today = PlaytimeService.format_last_played(now)
    assert "today" in result_today.lower() or result_today == "Today"
    
    result_yesterday = PlaytimeService.format_last_played(now - timedelta(days=1))
    assert "yesterday" in result_yesterday.lower() or result_yesterday == "Yesterday"
    
    result_2days = PlaytimeService.format_last_played(now - timedelta(days=2))
    assert "2" in result_2days and ("day" in result_2days.lower() or result_2days == "2 days ago")
    
    result_6days = PlaytimeService.format_last_played(now - timedelta(days=6))
    assert "6" in result_6days and ("day" in result_6days.lower() or result_6days == "6 days ago")

    # Old dates now use locale-aware format (%x)
    old_date = now - timedelta(days=10)
    result_old = PlaytimeService.format_last_played(old_date)
    # Just verify it returns a non-empty string (format depends on locale)
    assert len(result_old) > 0


def test_format_subtitle_with_data():
    """Test subtitle formatting with valid data and i18n."""
    from bottles.frontend.utils.playtime import PlaytimeRecord

    record = PlaytimeRecord(
        bottle_id="b1",
        program_id="p1",
        program_name="Game",
        program_path="/path",
        total_seconds=7325,
        sessions_count=3,
        last_played=datetime.now(),
    )

    service = PlaytimeService(MockManager(None))
    subtitle = service.format_subtitle(record)
    # Verify it contains the key elements (i18n strings may vary)
    assert "2h 02m" in subtitle  # Playtime format is not translated
    # Just verify the subtitle has content
    assert len(subtitle) > 10


def test_format_subtitle_never_played():
    """Test subtitle formatting with no data and i18n."""
    service = PlaytimeService(MockManager(None))
    result = service.format_subtitle(None)
    # i18n string may vary, but should contain "never" and "played"
    assert "never" in result.lower() or "played" in result.lower()


def test_service_disabled_returns_none():
    """Test that disabled service returns None."""
    with tempfile.TemporaryDirectory() as tmp:
        import os

        db_path = os.path.join(tmp, "test.db")
        tracker = ProcessSessionTracker(db_path=db_path, enabled=False)
        manager = MockManager(tracker)
        service = PlaytimeService(manager)

        assert not service.is_enabled()
        result = service.get_program_playtime("b1", "/bottle", "Game", "/path/game.exe")
        assert result is None
        tracker.shutdown()
