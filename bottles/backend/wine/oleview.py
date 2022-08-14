from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Oleview(WineProgram):
    program = "OLE/COM object viewer"
    command = "oleview"

