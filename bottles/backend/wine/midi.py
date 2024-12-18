from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.reg import Reg

class MIDI:
    instruments = {}

    @staticmethod
    def get_instrument_set(soundfont_path: str) -> int:
        """
        Get instrument set ID for given soundfont file.
        If not found, create a new one with the first vacant ID.
        """

        for idx, path in MIDI.instruments.items():
            if path == soundfont_path:
                return idx

        def get_vacant_id() -> int:
            n = len(MIDI.instruments)
            for idx in range(n):
                if idx not in MIDI.instruments:
                    return idx
            return n

        idx_new = get_vacant_id()
        MIDI.instruments[idx_new] = soundfont_path

        return idx_new

    @staticmethod
    def write_current_instrument_set(config: BottleConfig, soundfont_path: str):
        """Set program MIDI mapping to point to the right instrument set on launch."""

        idx = MIDI.get_instrument_set(soundfont_path)

        reg = Reg(config)
        reg.add(
            key="HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Multimedia\\MIDIMap",
            value="CurrentInstrument",
            data=f"#{idx}",
            value_type="REG_SZ",
        )
