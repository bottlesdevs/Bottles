# playtime.py
#
# Copyright 2025 Bottles Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
Playtime frontend service: retrieval, caching, and formatting of playtime data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from gettext import gettext as _
from typing import Dict, List, Optional, Tuple

from gi.repository import GLib

from bottles.backend.logger import Logger
from bottles.backend.managers.playtime import _compute_program_id


logging = Logger()


@dataclass(frozen=True)
class PlaytimeRecord:
    """Aggregated playtime data for a program or bottle."""

    bottle_id: str
    program_id: Optional[str]
    program_name: str
    program_path: Optional[str]
    total_seconds: int
    sessions_count: int
    last_played: Optional[datetime]


class PlaytimeCache:
    """Simple in-memory cache with TTL and manual invalidation."""

    def __init__(self, ttl_seconds: int = 30):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[Tuple[str, str], Tuple[PlaytimeRecord, float]] = {}

    def get(self, bottle_id: str, program_id: str) -> Optional[PlaytimeRecord]:
        key = (bottle_id, program_id)
        if key in self._cache:
            record, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                logging.debug(
                    f"Playtime cache hit: bottle={bottle_id} program_id={program_id}"
                )
                return record
            else:
                del self._cache[key]
                logging.debug(
                    f"Playtime cache expired: bottle={bottle_id} program_id={program_id}"
                )
        return None

    def set(self, bottle_id: str, program_id: str, record: PlaytimeRecord) -> None:
        key = (bottle_id, program_id)
        self._cache[key] = (record, time.time())
        logging.debug(f"Playtime cache set: bottle={bottle_id} program_id={program_id}")

    def invalidate(self, bottle_id: str, program_id: str) -> None:
        key = (bottle_id, program_id)
        if key in self._cache:
            del self._cache[key]
            logging.debug(
                f"Playtime cache invalidated: bottle={bottle_id} program_id={program_id}"
            )

    def clear(self) -> None:
        self._cache.clear()
        logging.debug("Playtime cache cleared")


class PlaytimeService:
    """
    Frontend service for accessing and formatting playtime data.

    Provides caching, retrieval, and human-readable formatting for playtime metrics.
    """

    def __init__(self, manager):
        """
        Initialize the playtime service.

        Args:
            manager: The Manager instance with playtime_tracker attribute.
        """
        self.manager = manager
        self.cache = PlaytimeCache(ttl_seconds=30)

    def is_enabled(self) -> bool:
        """Check if playtime tracking is currently enabled."""
        try:
            return self.manager.playtime_tracker.enabled
        except AttributeError:
            return False

    def get_program_playtime(
        self, bottle_id: str, bottle_path: str, program_name: str, program_path: str
    ) -> Optional[PlaytimeRecord]:
        """
        Retrieve playtime data for a specific program.

        Args:
            bottle_id: The bottle identifier.
            bottle_path: The bottle's full path (for path normalization).
            program_name: The program display name.
            program_path: The program executable path (used to compute program_id).

        Returns:
            PlaytimeRecord if data exists, None otherwise.
        """
        if not self.is_enabled():
            logging.debug("Playtime service: tracking disabled")
            return None

        program_id = _compute_program_id(bottle_id, bottle_path, program_path)
        logging.debug(
            f"Computed program_id: {program_id} for bottle={bottle_id}, path={program_path}"
        )

        # Check cache first
        cached = self.cache.get(bottle_id, program_id)
        if cached is not None:
            return cached

        # Fetch from backend
        try:
            logging.debug(
                f"Calling backend get_totals(bottle_id={bottle_id}, program_id={program_id})"
            )
            data = self.manager.playtime_tracker.get_totals(bottle_id, program_id)
            logging.debug(f"Backend returned: {data}")
            if data is None:
                logging.debug(f"No playtime data found for {program_name}")
                return None

            record = PlaytimeRecord(
                bottle_id=data["bottle_id"],
                program_id=data["program_id"],
                program_name=data["program_name"],
                program_path=data.get("program_path"),
                total_seconds=data["total_seconds"],
                sessions_count=data["sessions_count"],
                last_played=(
                    datetime.fromtimestamp(data["last_played"])
                    if data["last_played"] is not None
                    else None
                ),
            )
            logging.debug(f"Created record: {record}")
            self.cache.set(bottle_id, program_id, record)
            return record
        except Exception as e:
            logging.error(f"Failed to fetch playtime for {program_name}: {e}", exc=e)
            return None

    def get_bottle_playtime(self, bottle_id: str) -> Optional[PlaytimeRecord]:
        """
        Retrieve aggregated playtime data for an entire bottle.

        Aggregates all programs within the bottle client-side.

        Args:
            bottle_id: The bottle identifier.

        Returns:
            PlaytimeRecord with aggregated totals, or None if no data.
        """
        if not self.is_enabled():
            return None

        try:
            programs = self.manager.playtime_tracker.get_all_program_totals(bottle_id)
            if not programs:
                return None

            total_seconds = sum(p["total_seconds"] for p in programs)
            total_sessions = sum(p["sessions_count"] for p in programs)
            last_played_timestamps = [
                p["last_played"] for p in programs if p["last_played"] is not None
            ]
            last_played = (
                datetime.fromtimestamp(max(last_played_timestamps))
                if last_played_timestamps
                else None
            )

            # Use first program's bottle_name if available
            bottle_name = (
                programs[0].get("bottle_name", bottle_id) if programs else bottle_id
            )

            return PlaytimeRecord(
                bottle_id=bottle_id,
                program_id=None,
                program_name=bottle_name,
                program_path=None,
                total_seconds=total_seconds,
                sessions_count=total_sessions,
                last_played=last_played,
            )
        except Exception as e:
            logging.error(
                f"Failed to aggregate bottle playtime for {bottle_id}: {e}", exc=e
            )
            return None

    def invalidate_program(
        self, bottle_id: str, bottle_path: str, program_path: str
    ) -> None:
        """
        Invalidate cached data for a specific program.

        Args:
            bottle_id: The bottle identifier.
            bottle_path: The bottle's full path (for path normalization).
            program_path: The program executable path.
        """
        program_id = _compute_program_id(bottle_id, bottle_path, program_path)
        self.cache.invalidate(bottle_id, program_id)

    def invalidate_cache(self) -> None:
        """
        Clear all cached playtime data.

        Use this when you need to force a refresh of all playtime displays,
        such as after a program finishes running.
        """
        self.cache.clear()

    def get_weekly_data(
        self, bottle_id: str, program_id: str, week_offset: int = 0
    ) -> List[int]:
        """
        Retrieve weekly playtime data aggregated by day of week.

        Args:
            bottle_id: Bottle identifier
            program_id: Program identifier (SHA1 hash)
            week_offset: Week offset from current week (0=current, -1=last week, etc.)

        Returns:
            List of 7 integers representing minutes played per day.
            Index 0=Sunday, 1=Monday, ..., 6=Saturday.
            Returns [0, 0, 0, 0, 0, 0, 0] if tracking is disabled or on error.
        """
        if not self.is_enabled():
            logging.debug("Playtime service: tracking disabled")
            return [0] * 7

        try:
            get_weekly = getattr(self.manager.playtime_tracker, "get_weekly_playtime", None)
            if not callable(get_weekly):
                logging.error("Playtime service: get_weekly_playtime method not found")
                return [0] * 7

            data = get_weekly(bottle_id, program_id, week_offset)
            logging.debug(
                f"Retrieved weekly data: bottle_id={bottle_id} program_id={program_id} "
                f"week_offset={week_offset} data={data}"
            )
            return data

        except Exception:
            logging.error(
                f"Failed to retrieve weekly data: bottle_id={bottle_id} program_id={program_id} "
                f"week_offset={week_offset}",
                exc_info=True,
            )
            return [0] * 7

    def get_hourly_data(
        self, bottle_id: str, program_id: str, date_str: str
    ) -> List[int]:
        """
        Retrieve hourly playtime data (24-hour breakdown) for a specific date.

        Args:
            bottle_id: Bottle identifier
            program_id: Program identifier (SHA1 hash)
            date_str: Date in 'YYYY-MM-DD' format (e.g., '2025-11-20')

        Returns:
            List of 24 integers representing minutes played per hour.
            Index 0=00:00-00:59, 1=01:00-01:59, ..., 23=23:00-23:59.
            Returns [0]*24 if tracking is disabled or on error.
        """
        if not self.is_enabled():
            logging.debug("Playtime service: tracking disabled")
            return [0] * 24

        try:
            get_daily = getattr(self.manager.playtime_tracker, "get_daily_playtime", None)
            if not callable(get_daily):
                logging.error("Playtime service: get_daily_playtime method not found")
                return [0] * 24

            data = get_daily(bottle_id, program_id, date_str)
            logging.debug(
                f"Retrieved hourly data: bottle_id={bottle_id} program_id={program_id} "
                f"date={date_str} data={data}"
            )
            return data

        except Exception:
            logging.error(
                f"Failed to retrieve hourly data: bottle_id={bottle_id} program_id={program_id} "
                f"date={date_str}",
                exc_info=True,
            )
            return [0] * 24

    def get_monthly_data(self, bottle_id: str, program_id: str, year: int) -> List[int]:
        """
        Retrieve monthly playtime data for a specific year.

        Args:
            bottle_id: Bottle identifier
            program_id: Program identifier (SHA1 hash)
            year: Year as integer (e.g., 2025)

        Returns:
            List of 12 integers representing minutes played per month.
            Index 0=January, 1=February, ..., 11=December.
            Returns [0]*12 if tracking is disabled or on error.
        """
        if not self.is_enabled():
            logging.debug("Playtime service: tracking disabled")
            return [0] * 12

        try:
            get_monthly = getattr(self.manager.playtime_tracker, "get_monthly_playtime", None)
            if not callable(get_monthly):
                logging.error("Playtime service: get_monthly_playtime method not found")
                return [0] * 12

            data = get_monthly(bottle_id, program_id, year)
            logging.debug(
                f"Retrieved monthly data: bottle_id={bottle_id} program_id={program_id} "
                f"year={year} data={data}"
            )
            return data

        except Exception:
            logging.error(
                f"Failed to retrieve monthly data: bottle_id={bottle_id} program_id={program_id} "
                f"year={year}",
                exc_info=True,
            )
            return [0] * 12

    def get_weekly_session_count(
        self, bottle_id: str, program_id: str, week_offset: int = 0
    ) -> int:
        """Get the number of sessions for a specific week."""
        if not self.is_enabled():
            return 0

        try:
            get_count = getattr(self.manager.playtime_tracker, "get_weekly_session_count", None)
            if not callable(get_count):
                return 0
            return get_count(bottle_id, program_id, week_offset)
        except Exception as e:
            logging.error(f"Failed to get weekly session count: {e}", exc_info=True)
            return 0

    def get_daily_session_count(
        self, bottle_id: str, program_id: str, date_str: str
    ) -> int:
        """Get the number of sessions for a specific day."""
        if not self.is_enabled():
            return 0

        try:
            get_count = getattr(self.manager.playtime_tracker, "get_daily_session_count", None)
            if not callable(get_count):
                return 0
            return get_count(bottle_id, program_id, date_str)
        except Exception as e:
            logging.error(f"Failed to get daily session count: {e}", exc_info=True)
            return 0

    def get_yearly_session_count(
        self, bottle_id: str, program_id: str, year: int
    ) -> int:
        """Get the number of sessions for a specific year."""
        if not self.is_enabled():
            return 0

        try:
            get_count = getattr(self.manager.playtime_tracker, "get_yearly_session_count", None)
            if not callable(get_count):
                return 0
            return get_count(bottle_id, program_id, year)
        except Exception as e:
            logging.error(f"Failed to get yearly session count: {e}", exc_info=True)
            return 0

    @staticmethod
    def format_playtime(total_seconds: int) -> str:
        """
        Format playtime duration in human-readable form.

        Uses Python's timedelta for proper time formatting.

        Rules:
        - < 60s: "<1m"
        - < 3600s: "MMm"
        - < 86400s: "Hh MMm"
        - >= 86400s: "Dd HHh"

        Args:
            total_seconds: Total accumulated playtime in seconds.

        Returns:
            Formatted string.
        """
        if total_seconds < 60:
            return "<1m"

        td = timedelta(seconds=total_seconds)

        if total_seconds < 3600:
            # Less than an hour: show minutes only
            minutes = td.seconds // 60
            return f"{minutes}m"
        elif total_seconds < 86400:
            # Less than a day: show hours and minutes
            hours = td.seconds // 3600
            minutes = (td.seconds % 3600) // 60
            return f"{hours}h {minutes:02d}m"
        else:
            # A day or more: show days and hours
            days = td.days
            hours = td.seconds // 3600
            return f"{days}d {hours:02d}h"

    @staticmethod
    def format_last_played(last_played: Optional[datetime]) -> str:
        """
        Format last played timestamp in human-readable form.

        Rules:
        - None: "Never"
        - Today: "Today"
        - Yesterday: "Yesterday"
        - < 7 days: "N days ago"
        - Else: locale-aware date format

        Args:
            last_played: The datetime of last play session, or None.

        Returns:
            Formatted string.
        """
        if last_played is None:
            return _("Never")

        now = datetime.now()
        delta = now - last_played

        # Same day
        if last_played.date() == now.date():
            return _("Today")

        # Yesterday
        if last_played.date() == (now - timedelta(days=1)).date():
            return _("Yesterday")

        # Within last 7 days
        if delta.days < 7:
            # Translators: %d is the number of days
            return _("%d days ago") % delta.days

        # Older - use locale-aware format
        # Use locale's default date format via strftime with %x
        return last_played.strftime("%x")

    def format_subtitle(self, record: Optional[PlaytimeRecord]) -> str:
        """
        Generate a formatted subtitle string for display.

        Args:
            record: The playtime record, or None.

        Returns:
            Formatted subtitle like "Last Played: Today – Playtime: 1h 23m"
            or "Never Played" if no data.
        """
        if record is None or record.sessions_count == 0:
            return _("Never Played")

        last_played_str = self.format_last_played(record.last_played)
        playtime_str = self.format_playtime(record.total_seconds)

        # Escape for Pango markup to handle characters like < and >
        last_played_escaped = GLib.markup_escape_text(last_played_str)
        playtime_escaped = GLib.markup_escape_text(playtime_str)

        # Translators: %s placeholders are for date and playtime duration
        return _("Last Played: %s – Playtime: %s") % (
            last_played_escaped,
            playtime_escaped,
        )
