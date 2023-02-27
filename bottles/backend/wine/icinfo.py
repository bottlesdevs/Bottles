from typing import NewType

from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Icinfo(WineProgram):
    program = "List installed video compressors"
    command = "icinfo"

    def get_output(self):
        return self.launch(communicate=True, action_name="get_output")

    def get_dict(self):
        res = self.launch(communicate=True, action_name="get_dict")
        if not res.status or not res.data:
            return {}

        res = [r.strip() for r in res.split('\n')[1:]]
        _res = {}
        _latest = None

        for r in res:
            if not r:
                continue
            k, v = r.split(':')
            if r.startswith('vidc.'):
                _latest = k
                _res[k] = {}
                _res[k]['name'] = k
                _res[k]['description'] = v
            else:
                _res[_latest][k] = v

        return _res


        