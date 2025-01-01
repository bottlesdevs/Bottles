from ctypes import c_void_p
from fluidsynth import cfunc, Synth  # type: ignore[import-not-found]

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.reg import Reg

logging = Logger()


class FluidSynth:
    """Manages a FluidSynth instance bounded to an unique SoundFont (.sf2, .sf3) file."""

    __active_instances: dict[int, "FluidSynth"] = {}
    """Active FluidSynth instances (i.e currently in use by one or more programs)."""

    @classmethod
    def find_or_create(cls, soundfont_path: str) -> "FluidSynth":
        """
        Search for running FluidSynth instance and return it.
        If nonexistent, create and add it to active ones beforehand.
        """

        for fs in cls.__active_instances.values():
            if fs.soundfont_path == soundfont_path:
                return fs

        fs = cls(soundfont_path)
        cls.__active_instances[fs.id] = fs
        return fs

    def __init__(self, soundfont_path: str):
        """Build a new FluidSynth object from SoundFont file path."""
        self.soundfont_path = soundfont_path
        self.id = self.__get_vacant_id()
        self.__start()

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

    def delete(self):
        """
        Kill underlying synthetizer and remove FluidSynth instance from dict.
        Should be called only when no more programs are using it.
        """

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
