import fluidsynth

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.reg import Reg

logging = Logger()


class FluidSynth:
    """Manages a FluidSynth server bounded to a SoundFont (.sf2, .sf3) file."""

    __active_instances: dict[int, "FluidSynth"] = {}
    """Active FluidSynth instances (i.e currently in use by one or more programs)."""

    @classmethod
    def find_or_create(cls, soundfont_path: str) -> "FluidSynth":
        """
        Search for running FluidSynth instance and return it.
        If nonexistent, create and add SoundFont to active ones' dict beforehand.
        """

        for fs in cls.__active_instances.values():
            if fs.soundfont_path == soundfont_path:
                return fs

        fs = cls(soundfont_path)
        cls.__active_instances[fs.instrument_set_id] = fs
        return fs

    def __init__(self, soundfont_path: str):
        """Build a new FluidSynth object from SoundFont file path."""
        self.soundfont_path = soundfont_path
        self.instrument_set_id = self.__get_vacant_id()
        self.__run_server()

    @classmethod
    def __get_vacant_id(cls) -> int:
        """Get smallest 0-indexed ID currently not being used by a SoundFont."""
        n = len(cls.__active_instances)
        return next(i for i in range(n + 1) if i not in cls.__active_instances)

    def __run_server(self):
        """Create Synth object and start server with loaded SoundFont."""
        logging.info(
            "Starting new FluidSynth server with SoundFont"
            f" #{self.instrument_set_id} ('{self.soundfont_path}')…"
        )
        synth = fluidsynth.Synth()
        synth.start()
        sfid = synth.sfload(self.soundfont_path)
        synth.program_select(0, sfid, 0, 0)
        self.server = synth

    def register_as_current(self, config: BottleConfig):
        """
        Update Wine registry with SoundFont's ID, instructing
        MIDI mapping to load the correct instrument set on program startup.
        """
        reg = Reg(config)
        reg.add(
            key="HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Multimedia\\MIDIMap",
            value="CurrentInstrument",
            data=f"#{self.instrument_set_id}",
            value_type="REG_SZ",
        )

    def __del__(self):
        """
        Kill underlying server and remove SoundFont from dict
        when object instance is deallocated (i.e no programs using it anymore).
        """
        logging.info(
            "Killing FluidSynth server with SoundFont"
            f" #{self.instrument_set_id} ('{self.soundfont_path}')…"
        )
        self.server.delete()
        self.__active_soundfonts.pop(self.soundfont_path)
