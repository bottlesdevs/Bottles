from bottles.backend.wine.wineprogram import WineProgram


class Uninstaller(WineProgram):
    program = "Wine Uninstaller"
    command = "uninstaller"

    def get_uuid(self, name: str | None = None):
        args = " --list"

        if name is not None:
            args = f"--list | grep -i '{name}' | cut -f1 -d\\|"

        return self.launch(args=args, communicate=True, action_name="get_uuid")

    def from_uuid(self, uuid: str | None = None):
        args = ""

        if uuid not in [None, ""]:
            args = f"--remove {uuid}"

        return self.launch(args=args, action_name="from_uuid")

    def from_name(self, name: str):
        res = self.get_uuid(name)
        if not res.ready:
            """
            No UUID found, at this point it is safe to assume that the
            program is not installed
            ref: <https://github.com/bottlesdevs/Bottles/issues/2237>
            """
            return
        uuid = res.data.strip()
        for _uuid in uuid.splitlines():
            self.from_uuid(_uuid)
