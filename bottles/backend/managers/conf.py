import os
import json
from bottles.backend.utils import yaml
from configparser import ConfigParser


class ConfigManager(object):

    def __init__(self, config_file: str = None, config_type: str = 'ini', config_string: str = None):
        self.config_file = config_file
        self.config_string = config_string
        self.config_type = config_type

        if self.config_file is not None:
            self.checks()

        self.config_dict = self.read()

        if self.config_file is not None and self.config_string is not None:
            raise ValueError('Passing both config_file and config_string is not allowed')

    def checks(self):
        """Checks if the configuration file exists, if not, create it."""
        if not os.path.exists(self.config_file):
            base_path = os.path.dirname(self.config_file)
            os.makedirs(base_path, exist_ok=True)

            with open(self.config_file, 'w') as f:
                f.write('')

    def read(self):
        if self.config_file is not None:
            """Reads the configuration file and returns it as a dictionary"""
            if self.config_type == 'ini':
                config = ConfigParser()
                config.read(self.config_file)
                # noinspection PyProtectedMember
                res = config._sections
            elif self.config_type == 'json':
                with open(self.config_file, 'r') as f:
                    res = json.load(f)
            elif self.config_type == 'yaml' or self.config_type == 'yml' :
                with open(self.config_file, 'r') as f:
                    res = yaml.load(f)
            else:
                raise ValueError('Invalid configuration type')
        elif self.config_string is not None:
            if self.config_type == 'ini':
                config = ConfigParser()
                config.read_string(self.config_string)
                res = config._sections
            elif self.config_type == 'json':
                res = json.loads(self.config_string)
            elif self.config_type == 'yaml' or self.config_type == 'yml':
                res = yaml.load(self.config_string)
            else:
                raise ValueError('Invalid configuration type')
        else:
            res = None

        return res or {}

    def get_dict(self):
        """Returns the configuration as a dictionary"""
        return self.config_dict

    def write_json(self):
        """Writes the configuration to a JSON file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config_dict, f, indent=4)

    def write_yaml(self):
        """Writes the configuration to a YAML file"""
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config_dict, f)

    def write_ini(self):
        """Writes the configuration to an INI file"""
        config = ConfigParser()

        for section in self.config_dict:
            config.add_section(section)
            
            for key, value in self.config_dict[section].items():
                config.set(section, key, value)

        with open(self.config_file, 'w') as f:
            config.write(f)

    def write_dict(self, config_file: str=None):
        if self.config_file is None and config_file is None:
            raise ValueError('No config path specified')
        elif self.config_file is None and config_file is not None:
            self.config_file = config_file

        """Writes the configuration to the file"""
        if self.config_type == 'ini':
            self.write_ini()
        elif self.config_type == 'json':
            self.write_json()
        elif self.config_type == 'yaml':
            self.write_yaml()
        else:
            raise ValueError('Invalid configuration type')

    def merge_dict(self, changes: dict):
        """Merges a dictionary into the configuration"""
        for section in changes:
            if section in self.config_dict:
                for key, value in changes[section].items():
                    if isinstance(value, dict):
                        if key in self.config_dict[section]:
                            self.config_dict[section][key].update(value)
                        else:
                            self.config_dict[section][key] = value
                    else:
                        self.config_dict[section][key] = value
            else:
                self.config_dict[section] = changes[section]

        self.write_dict()

    def del_key(self, key_struct: dict):
        """Deletes a key from the configuration"""
        key = self.config_dict

        for i, k in enumerate(key_struct):
            if i == len(key_struct) - 1:
                del key[k]
                continue
            key = key[k]

        self.write_dict()
