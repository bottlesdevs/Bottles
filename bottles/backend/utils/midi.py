from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.reg import Reg


class SoundFont:
    """Encapsulates a SoundFont (.sf2, .sf3) file."""

    __active_soundfonts = {}
    """Dict of active SoundFonts (i.e currently being used by one or more programs)."""

    @classmethod
    def find_or_create(cls, soundfont_path: str) -> "SoundFont":
        """
        Search for SoundFont among the active ones and return it.
        If nonexistent, create and add it to the group beforehand.
        """
        if soundfont_path not in cls.__active_soundfonts:
            cls.__active_soundfonts[soundfont_path] = cls(soundfont_path)
        return cls.__active_soundfonts[soundfont_path]

    def __init__(self, soundfont_path: str):
        """Build new SoundFont object from file path."""
        self.soundfont_path = soundfont_path
        self.instrument_set_id = self.__get_vacant_id()

    @classmethod
    def __get_vacant_id(cls) -> int:
        """Get smallest ID currently not being used by a SoundFont."""
        n = len(cls.__active_soundfonts)
        active_ids = [sf.instrument_id for sf in cls.__active_soundfonts]
        return min(range(n + 1), key=(lambda i: i not in active_ids))

    def register_as_current(self, config: BottleConfig):
        """
        Update Wine registry with this SoundFont's ID,
        instructing MIDI mapping to load the correct instrument set on program startup.
        """
        reg = Reg(config)
        reg.add(
            key="HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Multimedia\\MIDIMap",
            value="CurrentInstrument",
            data=f"#{self.instrument_set_id}",
            value_type="REG_SZ",
        )
