from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Hh(WineProgram):
    program = "Wine HTML help viewer"
    command = "hh"
