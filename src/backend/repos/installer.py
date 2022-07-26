# installer.py
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
# pylint: disable=import-error,missing-docstring

from typing import Union
from bottles.backend.repos.repo import Repo  # pyright: reportMissingImports=false


class InstallerRepo(Repo):
    name = "installers"

    def get(self, name: str, plain: bool = False) -> Union[str, dict, bool]:
        if name in self.catalog:
            entry = self.catalog[name]
            url = f"{self.url}/{entry['Category']}/{name}.yml"
            return self.get_manifest(url, plain)
        return False

    def get_review(self, name: str) -> Union[str, bool]:
        if name in self.catalog:
            return self.get_manifest(f"{self.url}/Reviews/{name}.md", plain=True)
        return False

    def get_icon(self, name: str) -> Union[str, bytes, None]:
        if name in self.catalog:
            entry = self.catalog[name]
            icon = entry.get("Icon")
            if icon:
                return f"{self.url}/data/{name}/{icon}"
        return None
