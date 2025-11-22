"""Frontend playtime utilities and formatting helpers."""

from __future__ import annotations

import sqlite3
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

    def __init__(self, ttl_seconds: int = 30) -> None:
        self._ttl = max(0, int(ttl_seconds))
        self._cache: Dict[Tuple[str, Optional[str]], Tuple[PlaytimeRecord, float]] = {}

    def get(
        self, bottle_id: str, program_id: Optional[str]
    ) -> Optional[PlaytimeRecord]:
        key = (bottle_id, program_id)
        entry = self._cache.get(key)
        if entry is None:
            return None

        record, timestamp = entry
        if self._ttl and time.time() - timestamp > self._ttl:
            self._cache.pop(key, None)
            logging.debug(
                f"Playtime cache expired: bottle={bottle_id} program_id={program_id}"
            )
            return None

        logging.debug(f"Playtime cache hit: bottle={bottle_id} program_id={program_id}")
        return record

    def set(
        self, bottle_id: str, program_id: Optional[str], record: PlaytimeRecord
    ) -> None:
        key = (bottle_id, program_id)
        self._cache[key] = (record, time.time())
        logging.debug(f"Playtime cache set: bottle={bottle_id} program_id={program_id}")

    def invalidate(self, bottle_id: str, program_id: Optional[str]) -> None:
        key = (bottle_id, program_id)
        if key in self._cache:
            self._cache.pop(key, None)
            logging.debug(
                f"Playtime cache invalidated: bottle={bottle_id} program_id={program_id}"
            )

    def clear(self) -> None:
        self._cache.clear()
        logging.debug("Playtime cache cleared")


class PlaytimeService:
    """Frontend service for accessing and formatting playtime data."""

    def __init__(self, manager, ttl_seconds: int = 30) -> None:
        self._manager = manager
        self._cache = PlaytimeCache(ttl_seconds=ttl_seconds)

    def is_enabled(self) -> bool:
        tracker = self._tracker
        return bool(tracker and getattr(tracker, "enabled", False))

    def get_program_playtime(
        self,
        bottle_id: str,
        bottle_path: Optional[str],
        program_name: str,
        program_path: Optional[str],
        program_id: Optional[str] = None,
    ) -> Optional[PlaytimeRecord]:
        """Retrieve playtime data for a specific program."""

        if not self.is_enabled():
            logging.debug("Playtime service: tracking disabled")
            return None

        tracker = self._tracker
        if tracker is None:
            return None

        computed_program_id = program_id or self._compute_program_id(
            bottle_id, bottle_path, program_path
        )
        if computed_program_id is None:
            return None

        cached = self._cache.get(bottle_id, computed_program_id)
        if cached is not None:
            return cached

        data = self._fetch_program_totals(tracker, bottle_id, computed_program_id)
        if not data:
            return None

        record = PlaytimeRecord(
            bottle_id=bottle_id,
            program_id=computed_program_id,
            program_name=data.get("program_name") or program_name,
            program_path=data.get("program_path") or program_path,
            total_seconds=int(data.get("total_seconds", 0)),
            sessions_count=int(data.get("sessions_count", 0)),
            last_played=self._parse_timestamp(data.get("last_played")),
        )
        self._cache.set(bottle_id, computed_program_id, record)
        return record

    def get_bottle_playtime(self, bottle_id: str) -> Optional[PlaytimeRecord]:
        """Aggregate playtime data for an entire bottle."""

        if not self.is_enabled():
            logging.debug("Playtime service: tracking disabled")
            return None

        tracker = self._tracker
        if tracker is None:
            return None

        cached = self._cache.get(bottle_id, None)
        if cached is not None:
            return cached

        programs = self._fetch_all_program_totals(tracker, bottle_id)
        if not programs:
            return None

        total_seconds = sum(int(p.get("total_seconds", 0)) for p in programs)
        total_sessions = sum(int(p.get("sessions_count", 0)) for p in programs)

        timestamps: List[datetime] = []
        for program in programs:
            parsed = self._parse_timestamp(program.get("last_played"))
            if parsed is not None:
                timestamps.append(parsed)

        record = PlaytimeRecord(
            bottle_id=bottle_id,
            program_id=None,
            program_name=programs[0].get("bottle_name", bottle_id),
            program_path=None,
            total_seconds=total_seconds,
            sessions_count=total_sessions,
            last_played=max(timestamps) if timestamps else None,
        )
        self._cache.set(bottle_id, None, record)
        return record

    def invalidate_program(
        self,
        bottle_id: str,
        bottle_path: Optional[str],
        program_path: Optional[str],
        program_id: Optional[str] = None,
    ) -> None:
        """Invalidate cached data for a single program."""

        target_program_id = program_id or self._compute_program_id(
            bottle_id, bottle_path, program_path
        )
        if target_program_id is not None:
            self._cache.invalidate(bottle_id, target_program_id)

    def invalidate_cache(self) -> None:
        """Clear all cached playtime data."""

        self._cache.clear()

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

        tracker = self._tracker
        if tracker is None:
            logging.warning("Playtime service: tracker not available")
            return [0] * 7

        try:
            get_weekly = getattr(tracker, "get_weekly_playtime", None)
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

        tracker = self._tracker
        if tracker is None:
            logging.warning("Playtime service: tracker not available")
            return [0] * 24

        try:
            get_daily = getattr(tracker, "get_daily_playtime", None)
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

        tracker = self._tracker
        if tracker is None:
            logging.warning("Playtime service: tracker not available")
            return [0] * 12

        try:
            get_monthly = getattr(tracker, "get_monthly_playtime", None)
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

        tracker = self._tracker
        if tracker is None:
            return 0

        try:
            get_count = getattr(tracker, "get_weekly_session_count", None)
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

        tracker = self._tracker
        if tracker is None:
            return 0

        try:
            get_count = getattr(tracker, "get_daily_session_count", None)
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

        tracker = self._tracker
        if tracker is None:
            return 0

        try:
            get_count = getattr(tracker, "get_yearly_session_count", None)
            if not callable(get_count):
                return 0
            return get_count(bottle_id, program_id, year)
        except Exception as e:
            logging.error(f"Failed to get yearly session count: {e}", exc_info=True)
            return 0

    @staticmethod
    def format_playtime(total_seconds: int) -> str:
        """Format seconds into a human-readable playtime string."""

        if total_seconds < 60:
            return "<1m"

        td = timedelta(seconds=total_seconds)
        if total_seconds < 3600:
            minutes = td.seconds // 60
            return f"{minutes}m"
        if total_seconds < 86400:
            hours = td.seconds // 3600
            minutes = (td.seconds % 3600) // 60
            return f"{hours}h {minutes:02d}m"

        days = td.days
        hours = td.seconds // 3600
        return f"{days}d {hours:02d}h"

    @staticmethod
    def format_last_played(last_played: Optional[datetime]) -> str:
        """Format the last played timestamp with friendly labels."""

        if last_played is None:
            return _("Never")

        now = datetime.now()
        delta = now - last_played

        if last_played.date() == now.date():
            return _("Today")
        if last_played.date() == (now - timedelta(days=1)).date():
            return _("Yesterday")
        if delta.days < 7:
            return _("{} days ago").format(delta.days)

        glib_dt = GLib.DateTime.new_from_unix_local(int(last_played.timestamp()))
        formatted = glib_dt.format(_("%b %e, %Y"))
        return formatted if formatted is not None else ""

    def format_subtitle(self, record: Optional[PlaytimeRecord]) -> str:
        """Produce a subtitle string for UI labels."""

        if record is None or record.sessions_count == 0:
            return _("Never Played")

        last_played_str = self.format_last_played(record.last_played)
        playtime_str = self.format_playtime(record.total_seconds)

        last_played_escaped = GLib.markup_escape_text(last_played_str)
        playtime_escaped = GLib.markup_escape_text(playtime_str)
        return _("Last Played: %s – Playtime: %s") % (
            last_played_escaped,
            playtime_escaped,
        )

    @property
    def _tracker(self):
        return getattr(self._manager, "playtime_tracker", None)

    @staticmethod
    def _compute_program_id(
        bottle_id: str,
        bottle_path: Optional[str],
        program_path: Optional[str],
    ) -> Optional[str]:
        if not program_path:
            return None

        # New signature: _compute_program_id(bottle_id, program_path)
        return _compute_program_id(bottle_id, program_path)

    def _fetch_program_totals(
        self, tracker, bottle_id: str, program_id: str
    ) -> Optional[Dict[str, object]]:
        get_totals = getattr(tracker, "get_totals", None)
        if callable(get_totals):
            try:
                data = get_totals(bottle_id, program_id)
            except TypeError:
                data = get_totals(bottle_id=bottle_id, program_id=program_id)
            if data:
                return dict(data)

        return self._read_program_totals_from_db(tracker, bottle_id, program_id)

    def _fetch_all_program_totals(
        self, tracker, bottle_id: str
    ) -> List[Dict[str, object]]:
        get_all = getattr(tracker, "get_all_program_totals", None)
        if callable(get_all):
            try:
                programs = get_all(bottle_id)
            except TypeError:
                programs = get_all(bottle_id=bottle_id)
            if programs:
                return list(programs)

        return self._read_all_program_totals_from_db(tracker, bottle_id)

    @staticmethod
    def _read_program_totals_from_db(
        tracker, bottle_id: str, program_id: str
    ) -> Optional[Dict[str, object]]:
        db_path = getattr(tracker, "db_path", None)
        if not db_path:
            return None

        connection = None
        try:
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT bottle_id, bottle_name, program_id, program_name, program_path,
                       total_seconds, sessions_count, last_played
                FROM playtime_totals
                WHERE bottle_id=? AND program_id=?
                LIMIT 1
                """,
                (bottle_id, program_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logging.error(
                "Playtime service failed to read totals for bottle=%s program_id=%s: %s",
                bottle_id,
                program_id,
                exc,
                exc_info=True,
            )
            return None
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _read_all_program_totals_from_db(
        tracker, bottle_id: str
    ) -> List[Dict[str, object]]:
        db_path = getattr(tracker, "db_path", None)
        if not db_path:
            return []

        connection = None
        try:
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT bottle_id, bottle_name, program_id, program_name, program_path,
                       total_seconds, sessions_count, last_played
                FROM playtime_totals
                WHERE bottle_id=?
                """,
                (bottle_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logging.error(
                "Playtime service failed to read totals for bottle=%s: %s",
                bottle_id,
                exc,
                exc_info=True,
            )
            return []
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _parse_timestamp(value: Optional[object]) -> Optional[datetime]:
        if value in (None, "", 0):
            return None

        try:
            return datetime.fromtimestamp(int(value))
        except (ValueError, OSError, TypeError):
            return None
