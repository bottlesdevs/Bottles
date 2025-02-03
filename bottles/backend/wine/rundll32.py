from bottles.backend.wine.wineprogram import WineProgram


class RunDLL32(WineProgram):
    program = "32-bit DLLs loader and runner"
    command = "rundll32"
