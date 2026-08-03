from bottles.backend.utils.hidraw import list_hidraw_devices, normalize_hidraw_id


def test_list_hidraw_devices_reads_and_deduplicates_vid_pid(tmp_path):
    for index, name in ((0, "Flight Stick"), (1, "Duplicate Interface")):
        device = tmp_path / f"hidraw{index}" / "device"
        device.mkdir(parents=True)
        (device / "uevent").write_text(
            f"HID_ID=0003:0000044F:0000B10A\nHID_NAME={name}\n"
        )

    devices = list_hidraw_devices(tmp_path)

    assert len(devices) == 1
    assert devices[0].identifier == "0x044F/0xB10A"
    assert devices[0].name == "Flight Stick"


def test_list_hidraw_devices_ignores_malformed_entries(tmp_path):
    device = tmp_path / "hidraw0" / "device"
    device.mkdir(parents=True)
    (device / "uevent").write_text("HID_NAME=Missing identifier\n")

    assert list_hidraw_devices(tmp_path) == []


def test_normalize_hidraw_id_rejects_global_and_malformed_values():
    assert normalize_hidraw_id("0x044f/0xb10a") == "0x044F/0xB10A"
    assert normalize_hidraw_id("1") is None
    assert normalize_hidraw_id("0x044F") is None
