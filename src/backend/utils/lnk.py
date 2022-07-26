# lnk.py
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

import locale
import struct
from functools import lru_cache


class LnkUtils:

    @staticmethod
    @lru_cache
    def get_data(path):
        """
        Gets data from a .lnk file, and returns them in a dictionary.
        Thanks to @Winand and @Jared for the code.
        <https://gist.github.com/Winand/997ed38269e899eb561991a0c663fa49>
        """
        with open(path, 'rb') as stream:
            content = stream.read()
            '''
            Skip first 20 bytes (HeaderSize and LinkCLSID)
            read the LinkFlags structure (4 bytes)
            '''
            lflags = struct.unpack('I', content[0x14:0x18])[0]
            position = 0x18

            if (lflags & 0x01) == 1:
                '''
                If the HasLinkTargetIDList bit is set then skip the stored IDList 
                structure and header
                '''
                position = struct.unpack('H', content[0x4C:0x4E])[0] + 0x4E

            last_pos = position
            position += 0x04

            # get how long the file information is (LinkInfoSize)
            length = struct.unpack('I', content[last_pos:position])[0]

            '''
            Skip 12 bytes (LinkInfoHeaderSize, LinkInfoFlags and 
            VolumeIDOffset)
            '''
            position += 0x0C

            # go to the LocalBasePath position
            lbpos = struct.unpack('I', content[position:position + 0x04])[0]
            position = last_pos + lbpos

            # read the string at the given position of the determined length
            size = (length + last_pos) - position - 0x02
            content = content[position:position + size].split(b'\x00', 1)

            decode = locale.getdefaultlocale()[1]
            if len(content) > 1 or decode is None:
                decode = 'utf-16'

            try:
                return content[-1].decode(decode)
            except UnicodeDecodeError:
                return None
