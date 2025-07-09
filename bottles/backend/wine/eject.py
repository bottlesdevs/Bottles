from bottles.backend.wine.wineprogram import WineProgram


class Eject(WineProgram):
    program = "Wine Eject CLI"
    command = "eject"

    def cdrom(self, drive: str, unmount_only: bool = False):
        args = drive
        if unmount_only:
            args += " -u"
        return self.launch(args=args, communicate=True, action_name="cdrom")

    def all(self):
        args = "-a"
        return self.launch(args=args, communicate=True, action_name="all")
