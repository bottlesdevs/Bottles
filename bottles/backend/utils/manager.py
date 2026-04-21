# manager.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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
#
import os
import re
import shlex
import shutil
from gettext import gettext as _
from typing import Optional

import icoextract  # type: ignore [import-untyped]

from bottles.backend.params import APP_ID

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import SignalManager, Signals
from bottles.backend.utils.generic import get_mime
from bottles.backend.utils.imagemagick import ImageMagickUtils

from gi.repository import GLib, Gio, Xdp

portal = Xdp.Portal()

logging = Logger()


class ManagerUtils:
    """
    This class contains methods (tools, utilities) that are not
    directly related to the Manager.
    """

    @staticmethod
    def open_filemanager(
        config: Optional[BottleConfig] = None,
        path_type: str = "bottle",
        component: str = "",
        custom_path: str = "",
    ):
        logging.info("Opening the file manager in the path …")
        path = ""

        if path_type == "bottle" and config is None:
            raise NotImplementedError("bottle type need a valid Config")

        if path_type == "bottle":
            bottle_path = ManagerUtils.get_bottle_path(config)
            if config.Environment == "Steam":
                bottle_path = config.Path
            path = f"{bottle_path}/drive_c"
        elif component != "":
            if path_type in ["runner", "runner:proton"]:
                path = ManagerUtils.get_runner_path(component)
            elif path_type == "dxvk":
                path = ManagerUtils.get_dxvk_path(component)
            elif path_type == "vkd3d":
                path = ManagerUtils.get_vkd3d_path(component)
            elif path_type == "nvapi":
                path = ManagerUtils.get_nvapi_path(component)
            elif path_type == "latencyflex":
                path = ManagerUtils.get_latencyflex_path(component)
            elif path_type == "runtime":
                path = Paths.runtimes
            elif path_type == "winebridge":
                path = Paths.winebridge

        if path_type == "custom" and custom_path != "":
            path = custom_path

        path = f"file://{path}"
        SignalManager.send(Signals.GShowUri, Result(data=path))

    @staticmethod
    def get_bottle_path(config: BottleConfig) -> str:
        if config.Environment == "Steam":
            return os.path.join(Paths.steam, config.CompatData)

        if config.Custom_Path:
            return config.Path

        return os.path.join(Paths.bottles, config.Path)

    @staticmethod
    def get_runner_path(runner: str) -> str:
        if runner.startswith("sys-"):
            return runner
        return f"{Paths.runners}/{runner}"

    @staticmethod
    def get_dxvk_path(dxvk: str) -> str:
        return f"{Paths.dxvk}/{dxvk}"

    @staticmethod
    def get_vkd3d_path(vkd3d: str) -> str:
        return f"{Paths.vkd3d}/{vkd3d}"

    @staticmethod
    def get_nvapi_path(nvapi: str) -> str:
        return f"{Paths.nvapi}/{nvapi}"

    @staticmethod
    def get_latencyflex_path(latencyflex: str) -> str:
        return f"{Paths.latencyflex}/{latencyflex}"

    @staticmethod
    def get_temp_path(dest: str) -> str:
        return f"{Paths.temp}/{dest}"

    @staticmethod
    def get_template_path(template: str) -> str:
        return f"{Paths.templates}/{template}"

    @staticmethod
    def move_file_to_bottle(
        file_path: str, config: BottleConfig, fn_update: callable = None
    ) -> str | bool:
        logging.info(f"Adding file {file_path} to the bottle …")
        bottle_path = ManagerUtils.get_bottle_path(config)

        if not os.path.exists(f"{bottle_path}/storage"):
            """
            If the storage folder does not exist for the bottle,
            create it before moving the file.
            """
            os.makedirs(f"{bottle_path}/storage")

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_new_path = f"{bottle_path}/storage/{file_name}"

        logging.info(f"Copying file {file_path} to the bottle …")
        try:
            if file_size == 0:
                with open(file_new_path, "wb"):
                    pass
                if fn_update:
                    fn_update(1)
                return file_new_path

            chunk_size = 64 * 1024
            bytes_copied = 0
            with open(file_path, "rb") as f_in:
                with open(file_new_path, "wb") as f_out:
                    while True:
                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        bytes_copied += len(chunk)

                        if fn_update:
                            fn_update(bytes_copied / file_size)

                    if fn_update:
                        fn_update(1)
            return file_new_path
        except (OSError, IOError):
            logging.error(f"Could not copy file {file_path} to the bottle.")
            return False

    @staticmethod
    def get_exe_parent_dir(config, executable_path):
        """Get parent directory of the executable."""
        if "\\" in executable_path:
            p = "\\".join(executable_path.split("\\")[:-1])
            p = p.replace("C:\\", "\\drive_c\\").replace("\\", "/")
            return ManagerUtils.get_bottle_path(config) + p
        return os.path.dirname(executable_path)

    @staticmethod
    def extract_icon(config: BottleConfig, program_name: str, program_path: str) -> str:
        from bottles.backend.wine.winepath import WinePath

        winepath = WinePath(config)
        icon = "com.usebottles.bottles-program"
        bottle_icons_path = os.path.join(ManagerUtils.get_bottle_path(config), "icons")

        try:
            if winepath.is_windows(program_path):
                program_path = winepath.to_unix(program_path)

            ico_dest_temp = os.path.join(bottle_icons_path, f"_{program_name}.png")
            ico_dest = os.path.join(bottle_icons_path, f"{program_name}.png")
            ico = icoextract.IconExtractor(program_path)
            os.makedirs(bottle_icons_path, exist_ok=True)

            if os.path.exists(ico_dest_temp):
                os.remove(ico_dest_temp)

            if os.path.exists(ico_dest):
                os.remove(ico_dest)

            ico.export_icon(ico_dest_temp)
            # Some ICO files are incorrectly identified as TARGA
            # See https://bugs.astron.com/view.php?id=723
            if get_mime(ico_dest_temp) in ["image/vnd.microsoft.icon", "image/x-tga"]:
                if not ico_dest_temp.endswith(".ico"):
                    shutil.move(ico_dest_temp, f"{ico_dest_temp}.ico")
                    ico_dest_temp = f"{ico_dest_temp}.ico"
                im = ImageMagickUtils(ico_dest_temp)
                im.convert(ico_dest)
                icon = ico_dest
            else:
                shutil.move(ico_dest_temp, ico_dest)
                icon = ico_dest
        except:  # TODO: handle those
            pass

        return icon

    @staticmethod
    def create_desktop_entry(
        config,
        program: dict,
        skip_icon: bool = False,
        custom_icon: str = "",
    ):
        icon = "com.usebottles.bottles-program"

        if not skip_icon and not custom_icon:
            icon = ManagerUtils.extract_icon(
                config, program.get("name"), program.get("path")
            )
        elif custom_icon:
            icon = custom_icon

        def create_manual_fallback(icon_path, exec_cmd):
            """Create desktop entry manually when portal is unavailable."""
            filename = f"{config.get('Name')}-{program.get('name')}.desktop"
            content = (
                f"[Desktop Entry]\n"
                f"Exec={exec_cmd}\n"
                f"Type=Application\n"
                f"Terminal=false\n"
                f"Categories=Application;\n"
                f"Comment=Launch {program.get('name')} using Bottles.\n"
                f"StartupWMClass={program.get('name')}\n"
                f"Name={program.get('name')}\n"
                f"Icon={icon_path}\n"
            )

            # Write to application menu
            apps_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(apps_dir, exist_ok=True)
            apps_path = os.path.join(apps_dir, filename)
            try:
                with open(apps_path, "w") as f:
                    f.write(content)
                logging.info(f"Desktop entry created at {apps_path}")
            except Exception as e:
                logging.error(f"Failed to write desktop entry to applications: {e}")

            # Write to desktop surface
            desktop_dir = GLib.get_user_special_dir(
                GLib.UserDirectory.DIRECTORY_DESKTOP
            )
            if desktop_dir:
                desktop_path = os.path.join(desktop_dir, filename)
                try:
                    with open(desktop_path, "w") as f:
                        f.write(content)
                    # Make executable so KDE/GNOME will run it
                    os.chmod(desktop_path, 0o755)
                    logging.info(f"Desktop shortcut created at {desktop_path}")
                except Exception as e:
                    logging.error(f"Failed to write desktop shortcut: {e}")

            SignalManager.send(Signals.DesktopEntryCreated)

        def prepare_install_cb(self, result):
            exec_cmd = "bottles-cli run -p {} -b {} -- %u".format(
                shlex.quote(program.get("name")), shlex.quote(config.get("Name"))
            )

            # Handle portal preparation failure (e.g., KDE's broken implementation)
            try:
                ret = portal.dynamic_launcher_prepare_install_finish(result)
                if ret is None:
                    raise GLib.Error("Portal request was rejected or cancelled")
            except GLib.Error as e:
                logging.warning(
                    f"Dynamic Launcher portal preparation failed: {e}. "
                    "Falling back to manual creation."
                )
                create_manual_fallback(icon, exec_cmd)
                return

            launcher_id = f"{config.get('Name')}.{program.get('name')}"
            sum_type = GLib.ChecksumType.SHA1
            try:
                portal.dynamic_launcher_install(
                    ret["token"],
                    "{}.App_{}.desktop".format(
                        APP_ID,
                        GLib.compute_checksum_for_string(sum_type, launcher_id, -1),
                    ),
                    """[Desktop Entry]
                    Exec={}
                    Type=Application
                    Terminal=false
                    Categories=Application;
                    Comment=Launch {} using Bottles.
                    StartupWMClass={}""".format(
                        exec_cmd, program.get("name"), program.get("name")
                    ),
                )
                SignalManager.send(Signals.DesktopEntryCreated)
            except GLib.Error as e:
                logging.warning(
                    f"Dynamic Launcher portal install failed: {e}. "
                    "Falling back to manual creation."
                )
                create_manual_fallback(icon, exec_cmd)

        if icon != "com.usebottles.bottles-program" and not os.path.exists(icon):
            logging.warning(f"Icon file not found: {icon}. Falling back to default.")
            icon = "com.usebottles.bottles-program"

        if icon == "com.usebottles.bottles-program":
            icon += ".svg"
            _icon = Gio.File.new_for_uri(
                f"resource:/com/usebottles/bottles/icons/scalable/apps/{icon}"
            )
        else:
            _icon = Gio.File.new_for_path(icon)
        icon_v = Gio.BytesIcon.new(_icon.load_bytes()[0]).serialize()
        portal.dynamic_launcher_prepare_install(
            None,
            program.get("name"),
            icon_v,
            Xdp.LauncherType.APPLICATION,
            None,
            True,
            False,
            None,
            prepare_install_cb,
        )

    @staticmethod
    def browse_wineprefix(wineprefix: dict):
        """Presents a dialog to browse the wineprefix."""
        ManagerUtils.open_filemanager(
            path_type="custom", custom_path=wineprefix.get("Path")
        )

    @staticmethod
    def _get_desktop_entry_locations() -> list[str]:
        """Get the locations where desktop entries may be stored."""
        locations = [os.path.expanduser("~/.local/share/applications")]
        desktop_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)
        if desktop_dir:
            locations.append(desktop_dir)
        return locations

    @staticmethod
    def update_desktop_entries_on_rename(old_bottle_name: str, new_bottle_name: str):
        """
        Update desktop entries when a bottle is renamed.

        Searches for .desktop files by their Exec= line content (looking for
        bottles-cli with -b 'old_bottle_name'), updates the reference, and
        renames the file to match the new bottle name.
        """
        # Pattern to match bottles-cli command with the old bottle name
        bottle_pattern = re.compile(
            r"bottles-cli\s+run\s+.*-b\s+['\"]" + re.escape(old_bottle_name) + r"['\"]"
        )
        # Pattern to extract program name from Exec line
        program_pattern = re.compile(r"-p\s+['\"]([^'\"]+)['\"]")

        for location in ManagerUtils._get_desktop_entry_locations():
            if not os.path.isdir(location):
                continue

            for filename in os.listdir(location):
                if not filename.endswith(".desktop"):
                    continue

                file_path = os.path.join(location, filename)

                # Skip broken symlinks or non-existent files
                if not os.path.isfile(file_path):
                    continue

                try:
                    with open(file_path, "r") as f:
                        content = f.read()

                    # Check if this file references the old bottle name
                    if not bottle_pattern.search(content):
                        continue

                    # Extract program name for the new filename
                    program_match = program_pattern.search(content)
                    program_name = program_match.group(1) if program_match else None

                    # Update the Exec line to reference the new bottle name
                    content = re.sub(
                        r"(-b\s+)(['\"])" + re.escape(old_bottle_name) + r"\2",
                        r"\g<1>\g<2>" + new_bottle_name + r"\2",
                        content,
                    )

                    # Determine new file path
                    if program_name:
                        new_filename = f"{new_bottle_name}-{program_name}.desktop"
                        new_path = os.path.join(location, new_filename)
                    else:
                        new_path = file_path

                    with open(new_path, "w") as f:
                        f.write(content)

                    # Preserve executable permission for desktop files
                    if location == GLib.get_user_special_dir(
                        GLib.UserDirectory.DIRECTORY_DESKTOP
                    ):
                        os.chmod(new_path, 0o755)

                    # Remove old file if we renamed it
                    if new_path != file_path and os.path.exists(file_path):
                        os.remove(file_path)

                    if new_path != file_path:
                        logging.info(
                            f"Renamed desktop entry: {filename} -> {new_filename}"
                        )
                    else:
                        logging.info(f"Updated desktop entry: {filename}")
                except Exception as e:
                    logging.warning(f"Failed to update desktop entry {filename}: {e}")

    @staticmethod
    def update_desktop_entries_on_program_rename(
        bottle_name: str,
        old_program_name: str,
        new_program_name: str,
        bottle_path: Optional[str] = None,
    ):
        """
        Update desktop entries when a program is renamed.

        Searches for .desktop files by their Exec= line content (looking for
        bottles-cli with -p 'old_program_name' and -b 'bottle_name') and updates
        the references. If bottle_path is provided, also renames the icon file.
        """
        # Pattern to match bottles-cli command with the old program name and bottle
        program_pattern = re.compile(
            r"bottles-cli\s+run\s+.*-p\s+['\"]"
            + re.escape(old_program_name)
            + r"['\"].*-b\s+['\"]"
            + re.escape(bottle_name)
            + r"['\"]"
        )

        # Rename icon file if bottle_path is provided
        new_icon_path = None
        if bottle_path:
            icons_dir = os.path.join(bottle_path, "icons")
            old_icon_path = os.path.join(icons_dir, f"{old_program_name}.png")
            new_icon_path = os.path.join(icons_dir, f"{new_program_name}.png")
            if os.path.exists(old_icon_path):
                try:
                    shutil.move(old_icon_path, new_icon_path)
                    logging.info(
                        f"Renamed icon: {old_program_name}.png -> {new_program_name}.png"
                    )
                except Exception as e:
                    logging.warning(f"Failed to rename icon file: {e}")
                    new_icon_path = None

        for location in ManagerUtils._get_desktop_entry_locations():
            if not os.path.isdir(location):
                continue

            for filename in os.listdir(location):
                if not filename.endswith(".desktop"):
                    continue

                file_path = os.path.join(location, filename)

                # Skip broken symlinks or non-existent files
                if not os.path.isfile(file_path):
                    continue

                try:
                    with open(file_path, "r") as f:
                        content = f.read()

                    # Check if this file references the old program name in this bottle
                    if not program_pattern.search(content):
                        continue

                    # Update the Exec line to reference the new program name
                    content = re.sub(
                        r"(-p\s+)(['\"])" + re.escape(old_program_name) + r"\2",
                        r"\g<1>\g<2>" + new_program_name + r"\2",
                        content,
                    )

                    # Update Comment, Name, and StartupWMClass fields
                    content = re.sub(
                        r"(Comment=Launch\s+)"
                        + re.escape(old_program_name)
                        + r"(\s+using Bottles\.)",
                        r"\g<1>" + new_program_name + r"\2",
                        content,
                    )
                    content = re.sub(
                        r"(Name=)" + re.escape(old_program_name) + r"$",
                        r"\g<1>" + new_program_name,
                        content,
                        flags=re.MULTILINE,
                    )
                    content = re.sub(
                        r"(StartupWMClass=)" + re.escape(old_program_name) + r"$",
                        r"\g<1>" + new_program_name,
                        content,
                        flags=re.MULTILINE,
                    )

                    # Update Icon path if we successfully renamed the icon file
                    if new_icon_path:
                        old_icon_pattern = os.path.join(
                            bottle_path, "icons", f"{old_program_name}.png"
                        )
                        content = re.sub(
                            r"(Icon=)" + re.escape(old_icon_pattern) + r"$",
                            r"\g<1>" + new_icon_path,
                            content,
                            flags=re.MULTILINE,
                        )

                    # Rename the file to match the new program name
                    new_filename = f"{bottle_name}-{new_program_name}.desktop"
                    new_path = os.path.join(location, new_filename)

                    with open(new_path, "w") as f:
                        f.write(content)

                    # Preserve executable permission for desktop files
                    if location == GLib.get_user_special_dir(
                        GLib.UserDirectory.DIRECTORY_DESKTOP
                    ):
                        os.chmod(new_path, 0o755)

                    # Remove old file if we renamed it
                    if new_path != file_path and os.path.exists(file_path):
                        os.remove(file_path)

                    if new_path != file_path:
                        logging.info(
                            f"Renamed desktop entry: {filename} -> {new_filename}"
                        )
                    else:
                        logging.info(f"Updated desktop entry: {filename}")
                except Exception as e:
                    logging.warning(f"Failed to update desktop entry {filename}: {e}")

    @staticmethod
    def get_languages(
        from_name=None,
        from_locale=None,
        from_index=None,
        get_index=False,
        get_locales=False,
    ):
        locales = [
            "sys",
            "bg_BG",
            "cs_CZ",
            "da_DK",
            "de_DE",
            "el_GR",
            "en_US",
            "es_ES",
            "et_EE",
            "fi_FI",
            "fr_FR",
            "hr_HR",
            "hu_HU",
            "it_IT",
            "lt_LT",
            "lv_LV",
            "nl_NL",
            "no_NO",
            "pl_PL",
            "pt_PT",
            "ro_RO",
            "ru_RU",
            "sk_SK",
            "sl_SI",
            "sv_SE",
            "tr_TR",
            "zh_CN",
            "ja_JP",
            "zh_TW",
            "ko_KR",
        ]
        names = [
            _("System"),
            _("Bulgarian"),
            _("Czech"),
            _("Danish"),
            _("German"),
            _("Greek"),
            _("English"),
            _("Spanish"),
            _("Estonian"),
            _("Finnish"),
            _("French"),
            _("Croatian"),
            _("Hungarian"),
            _("Italian"),
            _("Lithuanian"),
            _("Latvian"),
            _("Dutch"),
            _("Norwegian"),
            _("Polish"),
            _("Portuguese"),
            _("Romanian"),
            _("Russian"),
            _("Slovak"),
            _("Slovenian"),
            _("Swedish"),
            _("Turkish"),
            _("Chinese"),
            _("Japanese"),
            _("Taiwanese"),
            _("Korean"),
        ]

        if from_name and from_locale:
            raise ValueError("Cannot pass both from_name, from_locale and from_index.")

        if from_name:
            if from_name not in names:
                raise ValueError("Given name not in list.")
            i = names.index(from_name)
            if get_index:
                return i
            return from_name, locales[i]

        if from_locale:
            if from_locale not in locales:
                raise ValueError("Given locale not in list.")
            i = locales.index(from_locale)
            if get_index:
                return i
            return from_locale, names[i]

        if isinstance(from_index, int):
            if from_index not in range(0, len(locales)):
                raise ValueError("Given index not in range.")
            return locales[from_index], names[from_index]

        if get_locales:
            return locales

        return names
