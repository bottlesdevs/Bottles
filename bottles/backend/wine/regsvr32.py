from bottles.backend.wine.wineprogram import WineProgram


class Regsvr32(WineProgram):
    program = "Wine DLL Registration Server"
    command = "regsvr32"

    def register(self, dll: str):
        args = f"/s {dll}"
        return self.launch(args=args, communicate=True, action_name="register")

    def unregister(self, dll: str):
        args = f"/s /u {dll}"
        return self.launch(args=args, communicate=True, action_name="unregister")

    def register_all(self, dlls: list):
        for dll in dlls:
            self.register(dll)

    def unregister_all(self, dlls: list):
        for dll in dlls:
            self.unregister(dll)
