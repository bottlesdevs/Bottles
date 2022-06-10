# imagemagick.py
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


class ImageMagick:
    def __init__(self, path: str):
        self.path = path

    @staticmethod
    def __validate_path(path: str):
        if os.path.exists(path):
            return False
        if os.path.isdir(path):
            return False
        return True

    def list_assets(self):
        res = subprocess.check_output(['identify', self.path]).decode('utf-8').split('\n')
        assets = []

        for r in res:
            _r = r.split(' ')
            if len(_r) < 3:
                continue
            assets.append(int(_r[2].split("x")[0]))
        return assets

    def convert(self, dest: str, asset_size: int = 256, resize: int = 0, flatten: bool = True):
        if not self.__validate_path(dest):
            raise FileExistsError("Destination path already exists")

        if asset_size not in self.list_assets():
            raise ValueError("Asset size not available")

        asset_index = self.list_assets().index(asset_size)
        cmd = f"convert {self.path}[{asset_index}]"

        if flatten:
            cmd += " -flatten"
        if resize > 0:
            cmd += f" -thumbnail {resize}x{resize}"

        cmd += f" {dest}"

        subprocess.Popen(["bash", "-c", cmd])
