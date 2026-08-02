# utils.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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
import webbrowser
from gettext import gettext as _


def format_runner_name(runner: str) -> str:
    if "FLATPAK_ID" in os.environ and runner.startswith("sys-wine-"):
        version = runner.removeprefix("sys-wine-")
        return _("Built-in Wine {version}").format(version=version)
    return runner


def open_doc_url(widget, page):
    webbrowser.open_new_tab(f"https://docs.usebottles.com/{page}")
