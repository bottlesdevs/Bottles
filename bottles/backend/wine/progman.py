from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Progman(WineProgram):
    program = "Wine Program Manager"
    command = "progman"

