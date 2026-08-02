# generic.py
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
import codecs
import contextlib
import functools
import os
import random
import re
import shlex
import string
import subprocess
from typing import Optional

import chardet

from bottles.backend.globals import locale_encodings


def validate_url(url: str):
    """Validate a URL."""
    regex = re.compile(
        r"^(?:http|ftp)s?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    return re.match(regex, url) is not None


def detect_encoding(text: bytes, locale_hint: str = None) -> Optional[str]:
    """
    Detect the encoding of a text by its bytes. Return None if it
    can't be detected.
    """
    if not text:  # when empty
        return "utf-8"
    if locale_hint:  # when hint available
        hint = locale_hint.split(".")
        match len(hint):
            case 1:
                loc = hint[0]
                if loc in locale_encodings:  # Use Windows locale defaults
                    return locale_encodings[loc]
            case 2:
                loc, encoding = hint
                try:
                    codecs.lookup(encoding)
                    return encoding
                except LookupError:  # Fallback to locale only
                    if loc in locale_encodings:
                        return locale_encodings[loc]
            case _:
                pass
    result = chardet.detect(text)
    encoding = result["encoding"]
    confidence = result["confidence"]
    if confidence < 0.5:
        return None
    return encoding


def is_glibc_min_available():
    """Check if the glibc minimum version is available."""
    try:
        import ctypes

        process_namespace = ctypes.CDLL(None)
        gnu_get_libc_version = process_namespace.gnu_get_libc_version
        gnu_get_libc_version.restype = ctypes.c_char_p
        version = gnu_get_libc_version().decode("ascii")
        if version >= "2.32":
            return version
    except:
        pass
    return False


NTSYNC_DEVICE = "/dev/ntsync"
NTSYNC_DEVICE_MARKER = b"/dev/ntsync"


@functools.lru_cache(maxsize=64)
def _wineserver_supports_ntsync(path: str, mtime_ns: int, size: int) -> bool:
    del mtime_ns, size
    try:
        with open(path, "rb") as binary:
            previous = b""
            while chunk := binary.read(1024 * 1024):
                data = previous + chunk
                if NTSYNC_DEVICE_MARKER in data:
                    return True
                previous = data[-len(NTSYNC_DEVICE_MARKER) :]
    except OSError:
        pass
    return False


def is_ntsync_available(runner: Optional[str] = None) -> bool:
    """
    Return True if both the kernel device and runner support ntsync.

    Runner names and Wine versions are not reliable capability indicators:
    distributions can build a recent Wine without the ntsync headers, while
    custom runners can backport it. The wineserver contains the device path
    only when ntsync support was compiled in.
    """
    if not os.path.exists(NTSYNC_DEVICE) or not os.access(NTSYNC_DEVICE, os.R_OK):
        return False
    if runner is None:
        return True

    try:
        runner_parts = shlex.split(runner)
    except ValueError:
        return False
    if len(runner_parts) != 1:
        return False

    wineserver = os.path.join(os.path.dirname(runner_parts[0]), "wineserver")
    try:
        stat = os.stat(wineserver)
    except OSError:
        return False

    return _wineserver_supports_ntsync(
        os.path.realpath(wineserver), stat.st_mtime_ns, stat.st_size
    )


def sort_by_version(_list: list, extra_check: str = "async"):
    def natural_keys(text):
        result = [int(re.search(extra_check, text) is None)]
        result.extend(
            [int(n) for n in re.findall(r"\d+", text)]
        )
        return result

    _list.sort(key=natural_keys, reverse=True)
    return _list


def get_mime(path: str):
    """Get the mime type of file."""
    with contextlib.suppress(FileNotFoundError):
        res = subprocess.check_output(["file", "--mime-type", path])
        if res:
            return res.decode("utf-8").split(":")[1].strip()
    return None


def random_string(length: int):
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(length)
    )
