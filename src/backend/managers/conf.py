import os
import json
import yaml
from configparser import ConfigParser


class ConfigManager(object):

    def __init__(self, config_file: str, config_type: str = 'ini'):
        self.config_file = config_file
        self.config_type = config_type
        self.checks()
        self.config_dict = self.read()

    def checks(self):
        """Checks if the configuration file exists, if not, create it."""
        if not os.path.exists(self.config_file):
            base_path = os.path.dirname(self.config_file)
            os.makedirs(base_path, exist_ok=True)
            with open(self.config_file, 'w') as f:
                f.write('')

    def read(self):
        """Reads the configuration file and returns it as a dictionary"""
        if self.config_type == 'ini':
            config = ConfigParser()
            config.read(self.config_file)
            res = config._sections
        elif self.config_type == 'json':
            with open(self.config_file, 'r') as f:
                res = json.load(f)
        elif self.config_type == 'yaml':
            with open(self.config_file, 'r') as f:
                res = yaml.safe_load(f)
        else:
            raise ValueError('Invalid configuration type')

        if res in [None, ""]:
            res = {}
        return res

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

    def write_dict(self):
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
