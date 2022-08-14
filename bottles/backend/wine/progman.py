from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Progman(WineProgram):
    program = "Wine Program Manager"
    command = "progman"

