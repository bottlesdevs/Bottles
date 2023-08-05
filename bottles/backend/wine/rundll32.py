
from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class RunDLL32(WineProgram):
    program = "32-bit DLLs loader and runner"
    command = "rundll32"
