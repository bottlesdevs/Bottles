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

from typing import Self

from ctypes import c_void_p
from fluidsynth import cfunc, Synth  # type: ignore [import-untyped]

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.reg import Reg

logging = Logger()


class FluidSynth:
    """FluidSynth instance bound to a unique SoundFont (.sf2, .sf3) file path."""

    __active_instances: dict[int, Self] = {}

    @classmethod
    def find_or_create(cls, soundfont_path: str) -> Self:
        """
        Search for running FluidSynth instance and return it.
        If nonexistent, create and add it to active ones beforehand.
        """

        for fs in cls.__active_instances.values():
            if fs.soundfont_path == soundfont_path:
                fs.program_count += 1
                return fs

        fs = cls(soundfont_path)
        cls.__active_instances[fs.id] = fs
        return fs

    def __init__(self, soundfont_path: str):
        """Build a new FluidSynth object from SoundFont file path."""
        self.soundfont_path = soundfont_path
        self.id = self.__get_vacant_id()
        self.__start()
        self.program_count = 1

    @classmethod
    def __get_vacant_id(cls) -> int:
        """Get smallest 0-indexed ID currently not in use by a SoundFont."""
        n = len(cls.__active_instances)
        return next(i for i in range(n + 1) if i not in cls.__active_instances)

    def __start(self):
        """Start FluidSynth synthetizer with loaded SoundFont."""
        logging.info(
            "Starting new FluidSynth server with SoundFont"
            f" #{self.id} ('{self.soundfont_path}')…"
        )
        synth = Synth(channels=16)
        synth.start()
        sfid = synth.sfload(self.soundfont_path)
        synth.program_select(0, sfid, 0, 0)
        self.synth = synth

    def register_as_current(self, config: BottleConfig):
        """
        Update Wine registry with this instance's ID, instructing
        MIDI mapping to load the correct instrument set on program startup.
        """
        reg = Reg(config)
        reg.add(
            key="HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Multimedia\\MIDIMap",
            value="CurrentInstrument",
            data=f"#{self.id}",
            value_type="REG_SZ",
        )

    def decrement_program_counter(self):
        """Decrement program counter; if it reaches zero, delete this instance."""
        self.program_count -= 1
        if self.program_count == 0:
            self.__delete()

    def __delete(self):
        """Kill underlying synthetizer and remove FluidSynth instance from dict."""

        def __delete_synth(synth: Synth):
            """Bind missing function and run deletion routines."""
            delete_fluid_midi_driver = cfunc(
                "delete_fluid_midi_driver", c_void_p, ("driver", c_void_p, 1)
            )
            delete_fluid_midi_driver(synth.midi_driver)
            synth.delete()

        logging.info(
            "Killing FluidSynth server with SoundFont"
            f" #{self.id} ('{self.soundfont_path}')…"
        )
        __delete_synth(self.synth)
        self.__active_instances.pop(self.id)
