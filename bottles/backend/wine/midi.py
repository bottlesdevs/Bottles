from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.reg import Reg

__active_soundfonts = {}


class SoundFont:
    """Encapsulates a SoundFont (.sf2, .sf3) file."""

    @classmethod
    def find_or_create(cls, soundfont_path: str) -> SoundFont:
        """
        Search for SoundFont among active ones.
        If nonexistent, create and add it to dict.
        """
        if soundfont_path not in __active_soundfonts:
            __active_soundfonts[soundfont_path] = cls(soundfont_path)
        return __active_soundfonts[soundfont_path]

    def __init__(self, soundfont_path: str):
        """Build new SoundFont object from file path."""
        self.soundfont_path = soundfont_path
        self.instrument_set_id = self.__get_vacant_id()

    def __get_vacant_id() -> int:
        """Get smallest ID currently not being used by a SoundFont."""
        n = len(__active_soundfonts)
        active_ids = [sf.instrument_id for sf in __active_soundfonts]
        return min(range(n + 1), key=(lambda i: i not in active_ids))

    def register_as_current(self, config: BottleConfig):
        """
        Write this SoundFont's ID to registry as the current instrument set,
        making Wine's MIDI mapping load it on program startup.
        """
        reg = Reg(config)
        reg.add(
            key="HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Multimedia\\MIDIMap",
            value="CurrentInstrument",
            data=f"#{self.instrument_set_id}",
            value_type="REG_SZ",
        )
