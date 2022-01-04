import os
import re
import uuid


class WinRegister:
    
    def new(self, path: str):
        '''
        This function creates a new WinRegister object
        with the given path.
        '''
        self.path = path
        self.diff = {} # will store last diff
        self.exclude = []
        self.reg_dict = self.__parse_dict(path)
        return self
    
    def __get_header(self):
        '''
        This function returns the header of the register.
        '''
        with open(self.path, "r") as reg:
            header = reg.readlines(4)
            return header
    
    def __parse_dict(self, path: str):
        '''
        This function parses the registry file and 
        return it in a dictionary.
        TODO: this use regex, tests seems to be ok but should
              be the first method to be checked if problems occur.
        '''
        _dict = {}
        exclude = [] # append here the keys to exclude, not safe

        with open(path, "r") as _reg:
            content = _reg.read()
            cur_line = 0
            regs = re.split("\n\n", content)

            for reg in regs:

                if cur_line <= 4:
                    '''
                    Skip the first 4 lines which are the
                    register header.
                    '''
                    cur_line += 1
                    continue
                
                for line in reg.split("\n"):
                    '''
                    Following checks will check the line format, when
                    one check succeed, continue to the next line.
                    '''

                    if line.startswith("["):
                        '''
                        Check if line format corresponds to a key, if
                        true, create a new key in the dictionary.
                        '''
                        key = line.strip("[]")
                        if any(key.startswith(ex) for ex in exclude):
                            key = None
                            continue
                        
                        _dict[key] = {}
                        continue
                     
                    if line.startswith("#time"):
                        '''
                        Check if line format corresponds to a time key, if
                        true get value and append to last key.
                        '''
                        if key is None:
                            continue

                        _dict[key]["time"] = line.split("=")[1]
                        continue

                    if line.startswith("\""):
                        '''
                        Check if line format corresponds to a value, if
                        true get key and value and append to last key.
                        '''
                        if key is None:
                            continue

                        _key = line.split("=")[0]
                        _value = line[len(_key)+2:]
                        _dict[key][_key] = _value
                        continue
        
        return _dict
    
    def compare(self, path: str=None, register: object=None):
        '''
        This function compares the current register with the
        given path and returns the difference.
        '''
        if path is not None:
            register = WinRegister().new(path)
        elif register is None:
            raise ValueError("No register given")
        
        diff = self.__get_diff(register)
        self.diff = diff
        return diff
    
    def __get_diff(self, register: object):
        '''
        This function returns the difference between the current
        register and the given register.
        '''
        diff = {}
        other_reg = register.reg_dict

        for key in self.reg_dict:

            if key not in other_reg:
                diff[key] = self.reg_dict[key]
                continue

            for _key in self.reg_dict[key]:

                if _key not in other_reg[key]:
                    diff[key] = self.reg_dict[key]
                    break
                
                if self.reg_dict[key][_key] != other_reg[key][_key]:
                    diff[key] = self.reg_dict[key]
                    break

        return diff
    
    def update(self, diff: dict = None):
        '''
        This function updates the current register with the
        given diff.
        '''
        if diff is None:
            diff = self.diff # use last diff

        for key in diff:
            self.reg_dict[key] = diff[key]
        
        if os.path.exists(self.path):
            '''
            Make a backup before overwriting the register.
            '''
            os.rename(self.path, f"{self.path}.{uuid.uuid4()}.bak")
        
        with open(self.path, "w") as reg:
            for h in self.__get_header():
                reg.write(h)

            for key in self.reg_dict:
                reg.write(f"[{key}]\n")
                for _key in self.reg_dict[key]:
                    if _key == "time":
                        reg.write(f"#time={self.reg_dict[key][_key]}\n")
                    else:
                        reg.write(f"{_key}={self.reg_dict[key][_key]}\n")
                reg.write("\n")
