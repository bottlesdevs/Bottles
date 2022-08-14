from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class WinHelp(WineProgram):
    program = "Microsoft help file viewer"
    command = "winhelp"
