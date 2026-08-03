import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


HIDRAW_CLASS_PATH = Path("/sys/class/hidraw")
HIDRAW_ID_PATTERN = re.compile(r"0x([0-9a-fA-F]{4})/0x([0-9a-fA-F]{4})")


@dataclass(frozen=True)
class HidrawDevice:
    identifier: str
    name: str


def normalize_hidraw_id(value) -> Optional[str]:
    if not isinstance(value, str):
        return None

    match = HIDRAW_ID_PATTERN.fullmatch(value.strip())
    if not match:
        return None

    return f"0x{match.group(1).upper()}/0x{match.group(2).upper()}"


def list_hidraw_devices(
    sys_class_path: Path = HIDRAW_CLASS_PATH,
) -> list[HidrawDevice]:
    devices = {}
    for entry in sorted(sys_class_path.glob("hidraw*")):
        try:
            properties = dict(
                line.split("=", 1)
                for line in (entry / "device" / "uevent").read_text().splitlines()
                if "=" in line
            )
            _, vendor, product = properties["HID_ID"].split(":")
            identifier = normalize_hidraw_id(
                f"0x{int(vendor, 16) & 0xFFFF:04X}/"
                f"0x{int(product, 16) & 0xFFFF:04X}"
            )
        except (KeyError, OSError, ValueError):
            continue

        if identifier and identifier not in devices:
            devices[identifier] = HidrawDevice(
                identifier=identifier,
                name=properties.get("HID_NAME") or identifier,
            )

    return sorted(devices.values(), key=lambda device: device.name.casefold())
