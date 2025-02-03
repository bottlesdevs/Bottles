from bottles.backend.wine.wineprogram import WineProgram


class Expand(WineProgram):
    program = "Wine cabinet expander"
    command = "expand"

    def extract(self, cabinet: str, filename: str):
        args = f"{cabinet} {filename}"
        return self.launch(args=args, communicate=True, action_name="extract")

    def extract_all(self, cabinet: str, filenames: list):
        for filename in filenames:
            self.extract(cabinet, filename)
