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

import re
import sys
import contextlib
import subprocess


def validate_url(url: str):
    """Validate a URL."""
    regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )

    return re.match(regex, url) is not None


def detect_encoding(text: bytes):
    """
    Detect the encoding of a text by its bytes. Return None if it
    can't be detected.
    """
    encodings = [
        "ascii",
        "utf-8",
        "utf-16",
        "utf-32",
        "latin-1",
        "big5",
        "gb2312",
        "gb18030",
        "euc_jp",
        "euc_jis_2004",
        "euc_jisx0213",
        "shift_jis",
        "shift_jis_2004",
        "shift_jisx0213",
        "iso2022_jp",
        "iso2022_jp_1",
        "iso2022_jp_2",
        "iso2022_jp_2004",
        "iso2022_jp_3",
        "iso2022_jp_ext",
        "iso2022_kr",
        "utf_32_be",
        "utf_32_le",
        "utf_16_be",
        "utf_16_le",
        "utf_7",
        "utf_8_sig",
        "utf_16_be_sig",
        "utf_16_le_sig",
        "utf_32_be_sig",
        "utf_32_le_sig"
    ]

    if sys.stdout is not None:
        encodings.append(sys.stdout.encoding)

    for encoding in encodings:
        with contextlib.suppress(UnicodeDecodeError):
            text.decode(encoding)
            return encoding

    return None


def is_glibc_min_available():
    """Check if the glibc minimum version is available."""
    try:
        import ctypes
        process_namespace = ctypes.CDLL(None)
        gnu_get_libc_version = process_namespace.gnu_get_libc_version
        gnu_get_libc_version.restype = ctypes.c_char_p
        version = gnu_get_libc_version().decode('ascii')
        if version >= '2.32':
            return version
    except:
        pass
    return False


def sort_by_version(_list: list, extra_check: str = "async"):
    def natural_keys(text):
        result = [int(re.search(extra_check, text) is None)]
        result.extend([int(c) for c in re.findall(r'\d+', text)])
        return result

    _list.sort(key=natural_keys, reverse=True)
    return _list


def get_mime(path: str):
    """Get the mime type of file."""
    with contextlib.suppress(FileNotFoundError):
        res = subprocess.check_output(["file", "--mime-type", path])
        if res:
            return res.decode('utf-8').split(':')[1].strip()
    return None
