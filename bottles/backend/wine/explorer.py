from bottles.backend.wine.wineprogram import WineProgram


class Explorer(WineProgram):
    program = "Wine Explorer"
    command = "explorer"

    def launch_desktop(
        self,
        desktop: str = "shell",
        width: int = 0,
        height: int = 0,
        program: str | None = None,
        args: str | None = None,
        environment: dict | None = None,
        cwd: str | None = None,
    ):
        _args = f"/desktop={desktop}"

        if width and height:
            _args += f",{width}x{height}"
        if program:
            _args += f" {program}"
        if args:
            _args += args

        return self.launch(
            args=_args,
            communicate=True,
            action_name="launch_desktop",
            environment=environment,
            cwd=cwd,
        )
