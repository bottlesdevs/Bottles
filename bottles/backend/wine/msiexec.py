from bottles.backend.wine.wineprogram import WineProgram


class MsiExec(WineProgram):
    program = "Wine MSI Installer"
    command = "msiexec"

    def install(
        self,
        pkg_path: str,  # or product code
        args: str = "",
        terminal: bool = False,
        cwd: str | None = None,
        environment: dict | None = None,
    ):
        args = f"/i {pkg_path} {args}"

        self.launch(
            args=args,
            communicate=True,
            minimal=True,
            environment=environment,
            terminal=terminal,
            cwd=cwd,
            action_name="install",
        )

    def repair(
        self,
        pkg_path: str,
        if_missing: bool = False,
        if_missing_or_outdated: bool = False,
        if_missing_or_outdated_or_same: bool = False,
        if_missing_or_different: bool = False,
        if_missing_or_hash_fail: bool = False,
        force_all: bool = False,
        all_user_registry_keys: bool = False,
        all_computer_registry_keys: bool = False,
        all_shortcuts: bool = False,
        recache: bool = False,
        cwd: str | None = None,
    ):
        """
        NOTICE: I have not been able to use the repair in any way, it seems to show
                no signs of life. This function is here for future needs, all options
                are mapped.
        """
        args = "/f"
        if if_missing:
            args += "p"
        elif if_missing_or_outdated:
            args += "o"
        elif if_missing_or_outdated_or_same:
            args += "e"
        elif if_missing_or_different:
            args += "d"
        elif if_missing_or_hash_fail:
            args += "c"
        elif force_all:
            args += "a"
        if all_user_registry_keys:
            args += "u"
        if all_computer_registry_keys:
            args += "m"
        if all_shortcuts:
            args += "s"
        if recache:
            args += "v"

        args += f" {pkg_path}"

        self.launch(
            args=args, communicate=True, minimal=True, cwd=cwd, action_name="repair"
        )

    def uninstall(self, pkg_path: str, cwd: str | None = None):
        args = f"/x {pkg_path}"
        self.launch(
            args=args, communicate=True, minimal=True, cwd=cwd, action_name="uninstall"
        )

    def apply_patch(self, patch: str, update: bool = False, cwd: str | None = None):
        args = f"/p {patch}"
        if update:
            args = f" /update {patch}"

        self.launch(
            args=args, communicate=True, minimal=True, cwd=cwd, action_name="apply_path"
        )

    def uninstall_patch(
        self, patch: str, product: str | None = None, cwd: str | None = None
    ):
        args = f"/uninstall {patch}"
        if product:
            args += f" /package {product}"

        self.launch(
            args=args,
            communicate=True,
            minimal=True,
            cwd=cwd,
            action_name="uninstall_patch",
        )

    def register_module(self, module: str, cwd: str | None = None):
        args = f"/y {module}"
        self.launch(
            args=args,
            communicate=True,
            minimal=True,
            cwd=cwd,
            action_name="register_module",
        )

    def unregister_module(self, module: str, cwd: str | None = None):
        args = f"/z {module}"
        self.launch(
            args=args,
            communicate=True,
            minimal=True,
            cwd=cwd,
            action_name="unregister_module",
        )
