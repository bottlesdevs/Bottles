from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class WineCfg(WineProgram):
    program = "Wine Configuration"
    command = "winecfg"
