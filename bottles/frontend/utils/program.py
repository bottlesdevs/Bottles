from gettext import gettext as _

from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync


def guard_program_launch(window, config, program, on_ready, on_check=None):
    def checked(exists, error=False):
        if on_check is not None:
            on_check(exists)
        if exists is False and not error:
            window.show_toast(_(
                "The program file could not be found. Check its path and any external drives."
            ))
            if not program.get("pre_script"):
                return
        on_ready()

    RunAsync(
        ManagerUtils.program_exists, callback=checked,
        config=config, path=program.get("path"),
    )
