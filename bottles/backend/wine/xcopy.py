from datetime import datetime

from bottles.backend.wine.wineprogram import WineProgram


class Xcopy(WineProgram):
    program = "Wine Xcopy implementation"
    command = "xcopy"

    def copy(
        self,
        source: str,
        dest: str,
        dir_and_subs: bool = False,
        keep_empty_dirs: bool = False,
        quiet: bool = False,
        full_log: bool = False,
        simulate: bool = False,
        ask_confirm: bool = False,
        only_struct: bool = False,
        no_overwrite_notify: bool = False,
        use_short_names: bool = False,
        only_existing_in_dest: bool = False,
        overwrite_read_only_files: bool = False,
        include_hidden_and_sys_files: bool = False,
        continue_if_error: bool = False,
        copy_attributes: bool = False,
        after_date: datetime | None = None,
    ):
        args = f"{source} {dest} /i"

        if dir_and_subs:
            args += "/s"
        if keep_empty_dirs:
            args += "/e"
        if quiet:
            args += "/q"
        if full_log:
            args += "/f"
        if simulate:
            args += "/l"
        if ask_confirm:
            args += "/w"
        if only_struct:
            args += "/t"
        if no_overwrite_notify:
            args += "/y"
        if use_short_names:
            args += "/n"
        if only_existing_in_dest:
            args += "/u"
        if overwrite_read_only_files:
            args += "/r"
        if include_hidden_and_sys_files:
            args += "/h"
        if continue_if_error:
            args += "/c"
        if copy_attributes:
            args += "/a"
        if after_date:
            if isinstance(after_date, datetime):
                args += f"/d:{after_date.strftime('%m-%d-%Y')}"

        return self.launch(args=args, communicate=True, action_name="start")
