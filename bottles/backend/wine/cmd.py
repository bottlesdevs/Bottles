from bottles.backend.wine.wineprogram import WineProgram


class CMD(WineProgram):
    program = "Wine Command Line"
    command = "cmd"

    def run_batch(
        self,
        batch: str,
        terminal: bool = True,
        args: str = "",
        environment: dict | None = None,
        cwd: str | None = None,
    ):
        args = f"/c {batch} {args}"

        self.launch(
            args=args,
            communicate=True,
            terminal=terminal,
            environment=environment,
            cwd=cwd,
            action_name="run_batch",
        )
