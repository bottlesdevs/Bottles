import subprocess

from bottles.backend.utils.imagemagick import ImageMagickUtils


def test_list_assets_passes_the_source_path_directly(monkeypatch):
    commands = []

    def check_output(command):
        commands.append(command)
        return b"game's icon.ico ICO 256x256 256x256+0+0 8-bit sRGB\n"

    monkeypatch.setattr(subprocess, "check_output", check_output)

    assets = ImageMagickUtils("game's icon.ico").list_assets()

    assert commands == [["magick", "identify", "game's icon.ico"]]
    assert assets == [256]


def test_convert_uses_imagemagick_seven_command(monkeypatch, tmp_path):
    commands = []
    source = tmp_path / "game icon.ico"
    destination = tmp_path / "game icon.png"
    source.write_text("icon", encoding="utf-8")
    image = ImageMagickUtils(str(source))

    monkeypatch.setattr(image, "list_assets", lambda: [16, 256])
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, check: commands.append((command, check)),
    )

    image.convert(str(destination))

    assert commands == [
        (
            [
                "magick",
                f"{source}[1]",
                "-thumbnail",
                "256x256",
                "-alpha",
                "on",
                "-background",
                "none",
                "-flatten",
                str(destination),
            ],
            False,
        )
    ]
