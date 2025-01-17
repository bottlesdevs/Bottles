# generic.py
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
import codecs
import contextlib
import random
import re
import string
import subprocess

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


def detect_encoding(text: bytes, locale_hint: str = None) -> str | None:
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


def sort_by_version(_list: list, extra_check: str = "async"):
    def natural_keys(text):
        result = [int(re.search(extra_check, text) is None)]
        result.extend(
            [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]
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
