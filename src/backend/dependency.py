# dependency.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import urllib.request
from typing import NewType
from datetime import datetime
from gi.repository import Gtk, GLib

from .runner import Runner
from .globals import BottlesRepositories, Paths
from ..utils import RunAsync

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)
RunnerName = NewType('RunnerName', str)
RunnerType = NewType('RunnerType', str)

class DependencyManager:

    def __init__(self):
        return

    def get_catalog(self, bottle: BottleConfig) -> list:
        return

    def install(self, bottle: BottleConfig) -> list:
        return

