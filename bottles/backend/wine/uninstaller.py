import shlex
from typing import Optional

from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Uninstaller(WineProgram):
    program = "Wine Uninstaller"
    command = "uninstaller"

    def get_uuid(self, name: Optional[str] = None):
        res = self.launch(args="--list 2>&1", communicate=True, action_name="get_uuid")

        if name is None or not res.ready:
            return res

        matches = []
        for line in res.data.splitlines():
            uuid, separator, display_name = line.partition("|||")
            if separator and name.casefold() in display_name.casefold():
                matches.append(uuid.strip())
        matches.reverse()
        res.data = "\n".join(matches)
        return res

    def from_uuid(self, uuid: Optional[str] = None):
        args = ""

        if uuid not in [None, ""]:
            args = f"--remove {shlex.quote(uuid)}"

        return self.launch(args=args, communicate=True, action_name="from_uuid")

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
