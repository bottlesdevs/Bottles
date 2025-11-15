# terminal.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import shlex
import subprocess

from bottles.backend.logger import Logger

logging = Logger()


class TerminalUtils:
    """
    This class is used to launch commands in the system terminal.
    It will loop all the "supported" terminals to find the one
    that is available, so it will be used to launch the command.
    """

    colors = {
        "default": "#00ffff #2b2d2e",
        "debug": "#ff9800 #2e2c2b",
        "easter": "#0bff00 #2b2e2c",
    }

    terminals = [
        # Part of Flatpak package
        ["easyterm.py", '-d -p "%s" -c %s'],
        # Third party
        ["foot", "%s"],
        ["kitty", "%s"],
        ["tilix", "-- %s"],
        ["st", "-e %s"],
        # Desktop environments
        ["xfce4-terminal", "-e %s"],
        ["konsole", "--noclose -e %s"],
        ["gnome-terminal", "-- %s"],
        ["kgx", "-e %s"],
        ["mate-terminal", "--command %s"],
        ["qterminal", "--execute %s"],
        ["lxterminal", "-e %s"],
        # Fallback
        ["xterm", "-e %s"],
    ]

    def __init__(self):
        self.terminal = None

    def check_support(self):
        if "FLATPAK_ID" in os.environ:
            self.terminal = self.terminals[0]
            return True

        for terminal in self.terminals:
            terminal_check = (
                subprocess.Popen(
                    f"command -v {terminal[0]} > /dev/null && echo 1 || echo 0",
                    shell=True,
                    stdout=subprocess.PIPE,
                )
                .communicate()[0]
                .decode("utf-8")
            )

            if "1" in terminal_check:
                self.terminal = terminal
                return True

        return False

    def execute(self, command, env=None, colors="default", cwd=None):
        if env is None:
            env = os.environ.copy()

        if not self.check_support():
            logging.warning("Terminal not supported.")
            return False

        if colors not in self.colors:
            colors = "default"

        # comando originale quotato
        command = shlex.quote(command)
        template = " ".join(self.terminal)
        term_bin = os.path.basename(self.terminal[0])

        # EasyTerm: due placeholder, colori + comando
        if "easyterm" in term_bin:
            palette = self.colors[colors]
            cmd_for_shell = shlex.quote(f"bash -c {command}")
            if "ENABLE_BASH" in os.environ:
                cmd_for_shell = "bash"
            full_cmd = template % (palette, cmd_for_shell)

        # xfce4-terminal: un placeholder
        elif term_bin == "xfce4-terminal":
            cmd_for_shell = shlex.quote(f"sh -c {command}")
            full_cmd = template % cmd_for_shell

        # kitty, foot, konsole, gnome-terminal: un placeholder
        elif term_bin in ["kitty", "foot", "konsole", "gnome-terminal"]:
            cmd_for_shell = shlex.quote(f"sh -c {command}")
            full_cmd = template % cmd_for_shell

        # fallback: un placeholder
        else:
            cmd_for_shell = shlex.quote(f"bash -c {command}")
            full_cmd = template % cmd_for_shell

        logging.info(f"Command: {full_cmd}")

        subprocess.Popen(
            full_cmd, shell=True, env=env, stdout=subprocess.PIPE, cwd=cwd
        ).communicate()[0].decode("utf-8")

        return True

    def launch_snake(self):
        snake_path = os.path.dirname(os.path.realpath(__file__))
        snake_path = os.path.join(snake_path, "snake.py")
        self.execute(command="python %s" % snake_path, colors="easter")
