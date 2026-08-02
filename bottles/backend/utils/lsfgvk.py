# lsfgvk.py
#
# Copyright 2026 Bottles Developers
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

import contextlib
import os
import shutil
import tempfile


def get_lsfg_vk_dll_path(bottle_path):
    return os.path.join(bottle_path, "lsfg-vk", "Lossless.dll")


def store_lsfg_vk_dll(source, bottle_path):
    if os.path.basename(source).casefold() != "lossless.dll":
        raise ValueError("Unexpected DLL name")

    with open(source, "rb") as file:
        if file.read(2) != b"MZ":
            raise ValueError("Invalid DLL")

    target = get_lsfg_vk_dll_path(bottle_path)
    target_dir = os.path.dirname(target)
    os.makedirs(target_dir, exist_ok=True)
    if os.path.exists(target) and os.path.samefile(source, target):
        return target

    fd, temporary = tempfile.mkstemp(dir=target_dir, prefix=".Lossless-", suffix=".dll")
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(temporary)
        raise

    return target


def remove_lsfg_vk_dll(bottle_path):
    target = get_lsfg_vk_dll_path(bottle_path)
    with contextlib.suppress(FileNotFoundError):
        os.remove(target)
    with contextlib.suppress(OSError):
        os.rmdir(os.path.dirname(target))
