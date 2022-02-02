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
    __journal: dict
    
    def __init__(self):
        self.__journal = {}
        self.__load_journal()
    
    def __load_journal(self):
        '''
        Load the journal file.
        '''
        if not os.path.exists(Paths.journal):
            logging.info("Creating journal file...")
            with open(Paths.journal, "w") as f:
                f.write("")
        with open(Paths.journal, "r") as f:
            self.__journal = yaml.safe_load(f)
        
    def __save_journal(self):
        '''
        Save the journal file.
        '''
        with open(Paths.journal, "w") as f:
            yaml.dump(self.__journal, f)
    
    def get(self, period: str = "today"):
        '''
        Return all events in the journal.
        '''
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
        
        return self.__filter_by_date(period)
    
    def __filter_by_date(self, date: str, period: str):
        '''
        Filter the journal by date.
        '''
        if period == "today":
            start = datetime.utcnow().date()
            end = start + timedelta(days=1)
        elif period == "yesterday":
            start = datetime.utcnow().date() - timedelta(days=1)
            end = start + timedelta(days=1)
        elif period == "week":
            start = datetime.utcnow().date() - timedelta(days=datetime.utcnow().weekday())
            end = start + timedelta(days=7)
        elif period == "month":
            start = datetime.utcnow().date().replace(day=1)
            end = start + timedelta(days=31)
        else:
            start = datetime.min
            end = datetime.max
        
        filtered_journal = {}
        for event_id, event in self.__journal.items():
            timestamp = datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S")
            if start <= timestamp <= end:
                filtered_journal[event_id] = event

        return filtered_journal
    
    def get_event(self, event_id: str):
        '''
        Return the event with the given ID.
        '''
        return self.__journal[event_id]
    
    def add_event(self, severity: str, message: str):
        '''
        Add an event to the journal.
        '''
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

        self.__journal[event_id] = {
            "severity": severity,
            "message": message,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.__save_journal()
        return event_id
