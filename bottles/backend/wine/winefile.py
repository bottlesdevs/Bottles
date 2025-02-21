from bottles.backend.wine.wineprogram import WineProgram


class WineFile(WineProgram):
    program = "Wine File Explorer"
    command = "winefile"

    def open_path(self, path: str = "C:\\\\"):
        args = path
        return self.launch(args=args, communicate=True, action_name="open_path")
