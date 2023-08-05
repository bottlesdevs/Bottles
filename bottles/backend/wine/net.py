from typing import Optional

from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Net(WineProgram):
    program = "Wine Services manager"
    command = "net"

    def start(self, name: Optional[str] = None):
        args = "start"

        if name is not None:
            args = f"start '{name}'"

        return self.launch(args=args, communicate=True, action_name="start")

    def stop(self, name: Optional[str] = None):
        args = "stop"

        if name is not None:
            args = f"stop '{name}'"

        return self.launch(args=args, communicate=True, action_name="stop")

    def use(self, name: Optional[str] = None):
        # this command has no documentation, not tested yet
        args = "use"

        if name is not None:
            args = f"use '{name}'"

        return self.launch(args=args, communicate=True, action_name="use")

    def list(self):
        services = []
        res = self.start()

        if not res.ready:
            return services

        lines = res.data.strip().splitlines()
        for r in lines[1:]:
            r = r[4:]
            services.append(r)

        return services
