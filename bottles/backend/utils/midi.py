# midi.py
#
# Copyright 2025 The Bottles Contributors
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


from fluidsynth import Synth  # type: ignore [import-untyped]

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.reg import Reg

logging = Logger()


class FluidSynth:
    """FluidSynth instance bound to a SoundFont (.sf2, .sf3) file."""

    def __init__(self, soundfont_path: str):
        """Build a new FluidSynth object from SoundFont file path."""
        self.soundfont_path = soundfont_path
        self.__start()

    def __start(self):
        """Start FluidSynth synthetizer with loaded SoundFont."""
        logging.info(
            "Starting new FluidSynth server with SoundFont"
            f" ('{self.soundfont_path}')…"
        )
        synth = Synth(channels=16)
        synth.start()
        sfid = synth.sfload(self.soundfont_path)
        synth.program_select(0, sfid, 0, 0)
        self.synth = synth
