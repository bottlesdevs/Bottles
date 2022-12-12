from typing import NewType

from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Taskmgr(WineProgram):
    program = "Wine Task Manager"
    command = "taskmgr"
