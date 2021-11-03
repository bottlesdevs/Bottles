from .globals import API
from .data import DataManager
from ..params import VERSION
import yaml
import urllib.request
from functools import lru_cache
from datetime import datetime, timedelta

class NotificationsManager:
    '''
    The NotificationsManager class is used to fetch and manage
    the notifications from the repository.
    '''

    messages = []
    data = DataManager()

    def __init__(self):
        self.__get_messages()
    
    @lru_cache
    def __get_messages(self):
        _messages = []

        try:
            with urllib.request.urlopen(API.notifications) as url:
                res = url.read().decode('utf-8')
                _messages = yaml.safe_load(res)
        except:
            _messages = []
        
        for message in _messages.items():
            message = message[1]
            _date = message.get("date")
            _date =  datetime(_date.year, _date.month, _date.day)

            if _date < datetime.today() - timedelta(days=1) and not message.get("recurrent"):
                    continue
            
            if message.get("id") in self.data.list().get("notifications"):
                continue

            if message.get("before") and message.get("before") == VERSION:
                continue

            self.messages.append(message)
    
    def mark_as_read(self, id):
        '''
        This function marks a notification as read, updating the
        user data file and marking the notification as read in the
        local list.
        '''
        for message in self.messages:
            if message.get("id") == id:
                message["read"] = True
                self.data.set("notifications", id)
                break