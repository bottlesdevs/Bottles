from .globals import Paths, Samples
from ..utils import UtilsLogger
import yaml

logging = UtilsLogger()

class DataManager:
    '''
    The DataManager class is used to store and retrieve data
    from the user data.yml file. Should be stored only info
    and settings that should not be stored in gsettings.
    '''

    __data = {}
    
    def __init__(self):
        self.__get_data()
    
    def __get_data(self):
        try:
            with open(Paths.data, 'r') as s:
                self.__data = yaml.safe_load(s)
        except FileNotFoundError:
            logging.error('Data file not found. Creating new one.')
            self.__create_data_file()
    
    def __create_data_file(self):
        with open(Paths.data, 'w') as s:
            yaml.dump(Samples.data, s)
        self.__get_data()
    
    def list(self):
        '''
        This function returns the whole data dictionary.
        '''
        return self.__data
    
    def set(self, key, value):
        '''
        This function sets a value in the data dictionary.
        '''
        if isinstance(self.__data[key], list):
            self.__data[key].append(value)
        else:
            self.__data[key] = value
        
        try:
            with open(Paths.data, 'w') as s:
                yaml.dump(self.__data, s)
        except FileNotFoundError:
            pass
    
    def get(self, key):
        '''
        This function returns the value of a key in the data dictionary.
        '''
        return self.__data[key]

