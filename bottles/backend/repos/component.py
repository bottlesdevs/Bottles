# component.py
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

from bottles.backend.repos.repo import Repo


class ComponentRepo(Repo):
    name = "components"

    def get(self, name: str, plain: bool = False) -> str | dict | bool:
        if not isinstance(name, str) or not name:
            return False
        if not isinstance(self.catalog, dict):
            return False

        entry = self.catalog.get(name)
        if not isinstance(entry, dict):
            return False

        category = entry.get("Category")
        subcategory = entry.get("Sub-category")
        if not isinstance(category, str) or not category:
            return False
        if subcategory is not None and not isinstance(subcategory, str):
            return False

        if subcategory:
            url = f"{self.url}/{category}/{subcategory}/{name}.yml"
        else:
            url = f"{self.url}/{category}/{name}.yml"

        return self.get_manifest(url, plain)
