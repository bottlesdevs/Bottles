# journal.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
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

import contextlib
import os
import shutil
import uuid
from datetime import datetime, timedelta
from typing import Optional

from bottles.backend.globals import Paths
from bottles.backend.utils import yaml


class JournalSeverity:
    """Represents the severity of a journal entry."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    CRASH = "crash"


class JournalManager:
    """
    Store and retrieve data from the journal file (YAML). This should
    contain only important Bottles events.
    """

    path = f"{Paths.base}/journal.yml"

    @staticmethod
    def __get_journal() -> dict:
        """Return the journal as a dictionary."""
        if not os.path.exists(JournalManager.path):
            with open(JournalManager.path, "w") as f:
                yaml.dump({}, f)

        with open(JournalManager.path, "r") as f:
            try:
                journal = yaml.load(f)
            except yaml.YAMLError:
                journal_backup = f"{JournalManager.path}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.bak"
                shutil.copy2(JournalManager.path, journal_backup)
                journal = {}

        if journal is None:
            return {}

        try:
            journal = {
                k: v
                for k, v in sorted(
                    journal.items(), key=lambda item: item[1]["timestamp"], reverse=True
                )
            }
        except (KeyError, TypeError):
            journal = {}

        return journal

    @staticmethod
    def __clean_old():
        """Clean old journal entries (1 month)."""
        journal = JournalManager.__get_journal()
        old_events = []
        latest = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for event_id, event in journal.items():
            if event.get("timestamp", None) is None:
                latest_datetime = datetime.strptime(latest, "%Y-%m-%d %H:%M:%S")
            else:
                latest_datetime = datetime.strptime(
                    event["timestamp"], "%Y-%m-%d %H:%M:%S"
                )
                latest = event["timestamp"]

            if latest_datetime < datetime.now() - timedelta(days=30):
                old_events.append(event_id)

        for event_id in old_events:
            del journal[event_id]

        JournalManager.__save_journal(journal)

    @staticmethod
    def __save_journal(journal: Optional[dict] = None):
        """Save the journal to the journal file."""
        if journal is None:
            journal = JournalManager.__get_journal()

        with contextlib.suppress(IOError, OSError):
            with open(JournalManager.path, "w") as f:
                yaml.dump(journal, f)

    @staticmethod
    def get(period: str = "today", plain: bool = False):
        """
        Return all events for the given period.
        Supported periods: all, today, yesterday, week, month
        Set plain to True to get the response as plain text.
        """
        journal = JournalManager.__get_journal()
        periods = [
            "all",
            "today",
            "yesterday",
            "week",
            "month",
        ]
        if period not in periods:
            period = "today"

        _journal = JournalManager.__filter_by_date(journal, period)

        if plain:
            _journal = yaml.dump(_journal, sort_keys=False, indent=4)

        return _journal

    @staticmethod
    def __filter_by_date(journal: dict, period: str):
        """Filter the journal by date."""
        _journal = {}
        if period == "today":
            start = datetime.now().date()
            end = start + timedelta(days=1)
        elif period == "yesterday":
            start = datetime.now().date() - timedelta(days=1)
            end = start + timedelta(days=1)
        elif period == "week":
            start = datetime.now().date() - timedelta(days=7)
            end = datetime.now().date() + timedelta(days=1)
        elif period == "month":
            start = datetime.now().date() - timedelta(days=30)
            end = datetime.now().date() + timedelta(days=1)
        elif period == "all":
            return journal
        else:
            start = datetime.now().date()
            end = start + timedelta(days=1)

        for event_id, event in journal.items():
            timestamp = datetime.strptime(
                event["timestamp"], "%Y-%m-%d %H:%M:%S"
            ).date()

            if start <= timestamp <= end:
                _journal[event_id] = event

        return _journal

    @staticmethod
    def get_event(event_id: str):
        """Return the event with the given id."""
        journal = JournalManager.__get_journal()
        return journal.get(event_id, None)

    @staticmethod
    def write(severity: JournalSeverity, message: str):
        """Write an event to the journal."""
        journal = JournalManager.__get_journal()
        event_id = str(uuid.uuid4())
        now = datetime.now()

        if severity not in JournalSeverity.__dict__.values():
            severity = JournalSeverity.INFO

        journal[event_id] = {
            "severity": severity,
            "message": message,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        }
        JournalManager.__save_journal(journal)
        JournalManager.__clean_old()
