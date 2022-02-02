# journal.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import yaml
import uuid
from datetime import datetime, timedelta

from bottles.backend.logger import Logger # pyright: reportMissingImports=false
from bottles.backend.globals import Paths

logging = Logger()

class JournalManager:
    '''
    The JournalManager class is used to store and retrieve data from the
    journal file, which is a YAML file containing all Bottles logged events.
    '''
    @staticmethod
    def __get_journal():
        '''
        Load the journal file.
        '''
        if not os.path.exists(Paths.journal):
            logging.info("Creating journal file...")
            with open(Paths.journal, "w") as f:
                f.write("")
        with open(Paths.journal, "r") as f:
            journal = yaml.safe_load(f)

        if journal is None:
            journal = {}
        return journal
    
    @staticmethod
    def __clean_old():
        '''
        Clean events old then 1 month.
        '''
        journal = JournalManager.__get_journal()
        old_events = []

        for event_id, event in journal.items():
            timestamp = datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S")
            if timestamp < datetime.now() - timedelta(days=30):
                old_events.append(event_id)
        for event_id in old_events:
            del journal[event_id]
        JournalManager.__save_journal(journal)

    @staticmethod
    def __save_journal(journal: dict = None):
        '''
        Save the journal to the journal file.
        '''
        if journal is None:
            journal = JournalManager.__get_journal()
        with open(Paths.journal, "w") as f:
            yaml.dump(journal, f)
    
    @staticmethod
    def get(period: str = "today", plain: bool = False):
        '''
        Return all events in the journal.
        '''
        journal = JournalManager.__get_journal()
        periods = [
            "all",
            "today",
            "yesterday",
            "week",
            "month",
        ]
        if period not in periods:
            logging.warning(f"Invalid period '{period}', falling back to 'today'")
            period = "today"
        
        _journal = JournalManager.__filter_by_date(journal, period)
        if plain:
            _journal = yaml.dump(_journal, sort_keys=False, indent=4)
        return _journal
    
    @staticmethod
    def __filter_by_date(journal: dict, period: str):
        '''
        Filter the journal by date.
        '''
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
            logging.error(f"Invalid period '{period}', falling back to 'today'")
            start = datetime.now().date()
            end = start + timedelta(days=1)

        for event_id, event in journal.items():
            timestamp = datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S").date()
            if start <= timestamp <= end:
                _journal[event_id] = event
        return _journal

    
    @staticmethod
    def get_event(event_id: str):
        '''
        Return the event with the given ID.
        '''
        journal = JournalManager.__get_journal()
        return journal.get(event_id, None)
    
    @staticmethod
    def write(severity: str, message: str):
        '''
        Add an event to the journal.
        '''
        journal = JournalManager.__get_journal()
        severities = [
            "info",
            "warning",
            "error",
        ]
        event_id = str(uuid.uuid4())
        now = datetime.now()

        if severity not in severities:
            logging.warning(f"Invalid severity '{severity}', falling back to 'info'")
            severity = "info"

        journal[event_id] = {
            "severity": severity,
            "message": message,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
        }
        JournalManager.__save_journal(journal)
        JournalManager.__clean_old()
