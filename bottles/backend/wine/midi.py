from typing import Optional

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
        
        for id, path in MIDI.instruments.items():
            if path == soundfont_path:
                return id
        
        def get_vacant_id() -> int:
            n = len(MIDI.instruments)
            for id in range(n):
                if id not in MIDI.instruments:
                    return id
            return n
        
        id_new = get_vacant_id()
        MIDI.instruments[id_new] = soundfont_path        

        return id_new

    @staticmethod
    def write_current_instrument_set(config: BottleConfig, soundfont_path: str):
        """Set program MIDI mapping to point to the right instrument set on launch."""

        id = MIDI.get_instrument_set(soundfont_path)

        reg = Reg(config)
        reg.add(
            key="HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Multimedia\\MIDIMap",
            value="CurrentInstrument",
            data=f"#{id}",
            value_type="REG_SZ",
        )
