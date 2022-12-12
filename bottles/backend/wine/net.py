from typing import NewType

from bottles.backend.logger import Logger
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


class Net(WineProgram):
    program = "Wine Services manager"
    command = "net"

    def start(self, name: str = None):
        args = "start"

        if name is not None:
            args = f"start '{name}'"

        return self.launch(args=args, communicate=True, action_name="start")

    def stop(self, name: str = None):
        args = "stop"

        if name is not None:
            args = f"stop '{name}'"

        return self.launch(args=args, communicate=True, action_name="stop")

    def use(self, name: str = None):
        # this command has no documentation, not tested yet
        args = "use"

        if name is not None:
            args = f"use '{name}'"

        return self.launch(args=args, communicate=True, action_name="use")

    def list(self):
        services = []
        res = self.start()

        if len(res) == 0:
            return services

        res = res.strip().splitlines()
        i = 0

        for r in res:
            if i == 0:
                i += 1
                continue

            r = r[4:]
            services.append(r)
            i += 1

        return services
