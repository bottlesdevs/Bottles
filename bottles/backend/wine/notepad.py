from bottles.backend.wine.wineprogram import WineProgram


class Notepad(WineProgram):
    program = "Wine Notepad"
    command = "notepad"

    def open(self, path: str, as_ansi: bool = False, as_utf16: bool = False):
        args = path
        if as_ansi:
            args = f"/a {path}"
        elif as_utf16:
            args = f"/w {path}"
        return self.launch(args=args, communicate=True, action_name="open")

    def print(self, path: str, printer_name: str | None = None):
        args = f"/p {path}"
        if printer_name:
            args = f"/pt {path} {printer_name}"
        return self.launch(args=args, communicate=True, action_name="print")
