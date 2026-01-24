# eagle.py
#
# Copyright 2026 mirkobrombin <brombin94@gmail.com>
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

import os
import time
import shutil
import uuid
import datetime
from glob import glob
import pefile
import patoolib
import yara
import struct
import json
import subprocess

from bottles.backend.globals import Paths
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import SignalManager, Signals
from bottles.backend.logger import Logger

from gi.repository import Gio, GLib

logging = Logger()

STEP_DELAY = 0.12 # to allow seeing the analysis progress


class EagleManager:
    """Windows executables analysis engine using pefile and YARA."""

    VS_PRODUCTS = {
        0x0104: "VS 2017", 0x0105: "VS 2017", 0x0106: "VS 2017",
        0x010A: "VS 2019", 0x010B: "VS 2019", 0x010C: "VS 2019",
        0x010D: "VS 2019", 0x010E: "VS 2019", 0x010F: "VS 2019",
        0x0114: "VS 2022", 0x0115: "VS 2022", 0x0116: "VS 2022",
        0x0117: "VS 2022", 0x0118: "VS 2022", 0x0119: "VS 2022",
        0x00FF: "VS 2015", 0x00EB: "VS 2013", 0x00D9: "VS 2012",
        0x00C7: "VS 2010", 0x0083: "VS 2008", 0x006D: "VS 2005",
    }

    DLL_MAPPINGS = {
        "d3d8.dll": ("DirectX 8", "Graphics"), "d3d9.dll": ("DirectX 9", "Graphics"),
        "d3d10.dll": ("DirectX 10", "Graphics"), "d3d11.dll": ("DirectX 11", "Graphics"),
        "d3d12.dll": ("DirectX 12", "Graphics"), "dxgi.dll": ("DXGI", "Graphics"),
        "d3dcompiler_47.dll": ("D3D Compiler", "Graphics"),
        "opengl32.dll": ("OpenGL", "Graphics"), "vulkan-1.dll": ("Vulkan", "Graphics"),
        "nvapi.dll": ("NVAPI", "Graphics"), "nvapi64.dll": ("NVAPI", "Graphics"),
        "amd_ags_x64.dll": ("AMD AGS", "Graphics"),
        "physx_loader.dll": ("PhysX", "Graphics"), "physx3_x64.dll": ("PhysX", "Graphics"),
        "d3dx9_43.dll": ("D3DX9", "Graphics"), "d3dx11_43.dll": ("D3DX11", "Graphics"),
        "nvngx_dlss.dll": ("DLSS", "Upscaling"), "nvngx_dlssg.dll": ("DLSS 3 Frame Gen", "Upscaling"),
        "libxess.dll": ("Intel XeSS", "Upscaling"),
        "ffx_fsr2_api_x64.dll": ("AMD FSR 2", "Upscaling"), "amd_fidelityfx_dx12.dll": ("AMD FSR", "Upscaling"),
        "amd_fidelityfx_vk.dll": ("AMD FSR", "Upscaling"),
        "xaudio2_7.dll": ("XAudio 2.7", "Audio"), "xaudio2_9.dll": ("XAudio 2.9", "Audio"),
        "x3daudio1_7.dll": ("X3DAudio", "Audio"),
        "fmod.dll": ("FMOD", "Audio"), "fmod64.dll": ("FMOD", "Audio"),
        "fmodstudio.dll": ("FMOD Studio", "Audio"),
        "wwise.dll": ("Wwise", "Audio"),
        "binkw32.dll": ("Bink", "Audio"), "binkw64.dll": ("Bink", "Audio"),
        "openal32.dll": ("OpenAL", "Audio"), "dsound.dll": ("DirectSound", "Audio"),
        "miles32.dll": ("Miles", "Audio"), "mss32.dll": ("Miles", "Audio"),
        "mscoree.dll": (".NET Framework", "Runtimes"),
        "clr.dll": (".NET CLR", "Runtimes"),
        "hostfxr.dll": (".NET Core/5+", "Runtimes"),
        "coreclr.dll": (".NET Core CLR", "Runtimes"),
        "msvcp100.dll": ("VC++ 2010", "Runtimes"), "msvcr100.dll": ("VC++ 2010", "Runtimes"),
        "msvcp110.dll": ("VC++ 2012", "Runtimes"), "msvcr110.dll": ("VC++ 2012", "Runtimes"),
        "msvcp120.dll": ("VC++ 2013", "Runtimes"), "msvcr120.dll": ("VC++ 2013", "Runtimes"),
        "msvcp140.dll": ("VC++ 2015-22", "Runtimes"), "vcruntime140.dll": ("VC++ 2015-22", "Runtimes"),
        "vcruntime140_1.dll": ("VC++ 2015-22", "Runtimes"),
        "ucrtbase.dll": ("UCRT", "Runtimes"),
        "mono-2.0-bdwgc.dll": ("Mono", "Runtimes"),
        "jvm.dll": ("Java", "Runtimes"),
        "python3.dll": ("Python", "Runtimes"), "python311.dll": ("Python 3.11", "Runtimes"),
        "lua54.dll": ("Lua 5.4", "Runtimes"),
        "xinput1_3.dll": ("XInput 1.3", "Input"), "xinput1_4.dll": ("XInput 1.4", "Input"),
        "dinput8.dll": ("DirectInput", "Input"),
        "sdl2.dll": ("SDL2", "Input"),
        "steam_api.dll": ("Steamworks", "Social/DRM"), "steam_api64.dll": ("Steamworks", "Social/DRM"),
        "galaxy.dll": ("GOG Galaxy", "Social/DRM"), "galaxy64.dll": ("GOG Galaxy", "Social/DRM"),
        "eossdk-win64-shipping.dll": ("Epic", "Social/DRM"),
        "discord_game_sdk.dll": ("Discord", "Social/DRM"),
        "uplay_r1_loader64.dll": ("Ubisoft", "Social/DRM"),
        "unityplayer.dll": ("Unity", "Engines"), "gameassembly.dll": ("Unity IL2CPP", "Engines"),
        "libcef.dll": ("CEF", "Engines"),
        "tier0.dll": ("Source", "Engines"), "vstdlib.dll": ("Source", "Engines"),
        "cryrenderd3d11.dll": ("CryEngine", "Engines"),
        "qt5core.dll": ("Qt 5", "Frameworks"), "qt6core.dll": ("Qt 6", "Frameworks"),
        "electron.dll": ("Electron", "Frameworks"),
        "easyanticheat.dll": ("EAC", "Protection"), "easyanticheat_x64.dll": ("EAC", "Protection"),
        "battleye.dll": ("BattlEye", "Protection"), "beclient_x64.dll": ("BattlEye", "Protection"),
        "vmprotectsdk64.dll": ("VMProtect", "Protection"),
        "denuvo64.dll": ("Denuvo", "Protection"),
    }

    PACKER_SECTIONS = {
        "UPX0": "UPX", "UPX1": "UPX", ".upx": "UPX",
        ".vmp0": "VMProtect", ".vmp1": "VMProtect", "VMP0": "VMProtect",
        ".themida": "Themida",
        ".enigma": "Enigma",
    }

    _yara_rules = None

    def __init__(self, config: BottleConfig):
        self.config = config
        self._load_yara_rules()

    @classmethod
    def _load_yara_rules(cls) -> None:
        """Load YARA rules from the bundled file."""

        logging.info("[Eagle] Reloading YARA rules...")
        rules_path = os.path.join(os.path.dirname(__file__), "eagle.yar")
        if os.path.exists(rules_path):
            try:
                cls._yara_rules = yara.compile(filepath=rules_path)
                logging.info("[Eagle] YARA rules loaded")
            except Exception as e:
                logging.warning(f"[Eagle] Failed to load YARA rules: {e}")
                cls._yara_rules = None

    def _is_safe_neighbor_dir(self, directory: str) -> bool:
        """Check if directory is safe for neighbor scanning (not a common clutter folder)."""
        try:
            path = os.path.realpath(directory)
            
            if "/run/user/" in path and "/doc/" in path:
                logging.info(f"[Eagle] Blocking neighbor scan for portal path: {path}")
                return False

            unsafe_dirs = {
                GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD),
                GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP),
                GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS),
                GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_TEMPLATES),
                GLib.get_home_dir()
            }

            unsafe_paths = {os.path.realpath(p) for p in unsafe_dirs if p}
            if path in unsafe_paths or path == os.path.realpath(os.path.expanduser("~")):
                logging.info(f"[Eagle] Neighbor scan blocked for unsafe path: {path}")
                return False
                
            return True
        except Exception as e:
            logging.warning(f"[Eagle] Error checking directory safety: {e}")
            return True

    def _send_step(self, msg: str, delay: bool = True) -> None:
        """Send a step update to the UI with optional delay."""
        SignalManager.send(Signals.EagleStep, Result(status=True, data=msg))
        logging.info(f"[Eagle] {msg}")
        if delay:
            time.sleep(STEP_DELAY)

    def _scan_yara(self, file_path: str, insights: dict, source: str = "Main Executable") -> list:
        """Run YARA scan on a file and update insights."""
        if self._yara_rules is None:
            return []

        matches = []
        try:
            results = self._yara_rules.match(file_path, timeout=30)
            for match in results:
                category = match.meta.get('category', 'Unknown')
                name = match.meta.get('name', match.rule)
                warning_desc = match.meta.get('description', '')
                severity = match.meta.get('severity', 'info')

                if category not in insights:
                    insights[category] = []
                
                existing_names = [i['name'] for i in insights[category]] if isinstance(insights[category], list) else []
                context = []
                for valid_match in match.strings:
                    ident = None
                    data = None
                    
                    if isinstance(valid_match, tuple):
                        _, ident, data = valid_match
                    else:
                         try:
                             ident = valid_match.identifier
                             if hasattr(valid_match, "instances") and valid_match.instances:
                                 data = valid_match.instances[0].matched_data
                         except:
                             continue
                    
                    rule_name = match.rule
                    should_capture = False
                    
                    if ident and data:
                        if ident == "$capture":
                            should_capture = True
                        elif "key" in ident or "reg" in ident:
                             should_capture = True
                        elif rule_name in ["Node_System_Commands", "Node_Native_Module", "Node_Kernel_Driver", "Driver_Service"]:
                            should_capture = True

                    if should_capture:
                        try:
                            decoded = data.decode('utf-16le') if b'\x00' in data else data.decode('utf-8')
                            clean = decoded.strip().replace('\x00', '')
                            
                            clean_upper = clean.upper()
                            roots = ["HKEY_LOCAL_MACHINE", "HKEY_CURRENT_USER", "HKLM", "HKCU", "HKLM\\", "HKCU\\"]
                            
                            if clean_upper not in roots and len(clean) > 2 and clean not in context:
                                context.append(clean)
                        except:
                            pass
                
                context_list = context[:20]

                if name not in existing_names:
                    if category == "Warning":
                        insights[category].append({
                            "name": name,
                            "description": warning_desc,
                            "severity": severity,
                            "source": source,
                            "context": context_list
                        })
                        self._send_step(f"[!] Warning: {name} ({source})")
                    else:
                        insights[category].append({
                            "name": name,
                            "source": source,
                            "context": context_list
                        })
                        self._send_step(f"[{category}] {name} ({source})", delay=False)
                matches.append({"rule": match.rule, "category": category, "name": name, "severity": severity, "source": source})
        except Exception as e:
            logging.error(f"[Eagle] YARA scan failed on {file_path}: {e}")

        return matches

    def _extract_asar(self, asar_path: str) -> tuple:
        """Extract ASAR archive using pure Python."""
        extract_dir = os.path.join(Paths.temp, f"eagle_asar_{uuid.uuid4().hex[:8]}")
        os.makedirs(extract_dir, exist_ok=True)
        extracted_files = []

        try:
            self._send_step(f"Extracting ASAR archive: {os.path.basename(asar_path)}...")
            with open(asar_path, 'rb') as f:
                data = f.read(16)
                if len(data) < 16:
                    return [], None
                
                header_json_len = struct.unpack('<I', data[12:16])[0]
                
                header_json_data = f.read(header_json_len)
                header = json.loads(header_json_data.decode('utf-8'))
                
                # Base offset for files
                base_offset = 16 + header_json_len
                
                def walk_files(dir_structure, current_path=""):
                    if "files" in dir_structure:
                        for name, info in dir_structure["files"].items():
                            new_path = os.path.join(current_path, name)
                            if "files" in info:
                                # Directory
                                os.makedirs(os.path.join(extract_dir, new_path), exist_ok=True)
                                walk_files(info, new_path)
                            elif "offset" in info and "size" in info:
                                # File
                                try:
                                    ext = os.path.splitext(name)[1].lower()
                                    if ext not in [".js", ".json", ".node", ".html", ".htm"]:
                                        continue

                                    offset = int(info["offset"]) + base_offset
                                    size = int(info["size"])
                                    
                                    out_path = os.path.join(extract_dir, new_path)
                                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                                    
                                    current_pos = f.tell()
                                    f.seek(offset)
                                    content = f.read(size)
                                    f.seek(current_pos)
                                    
                                    with open(out_path, 'wb') as out_f:
                                        out_f.write(content)
                                    
                                    extracted_files.append(out_path)
                                except Exception as e:
                                    logging.warning(f"[Eagle] Failed to extract {new_path}: {e}")

                walk_files(header)
                self._send_step(f"Extracted {len(extracted_files)} files from ASAR")
                return extracted_files, extract_dir

        except Exception as e:
            logging.error(f"[Eagle] ASAR extraction failed: {e}")
            return [], None

    def _extract_installer(self, installer_path: str, installer_type: str) -> tuple:
        """Extract installer and return list of extracted exe/dll paths."""
        extract_dir = os.path.join(Paths.temp, f"eagle_{uuid.uuid4().hex[:8]}")
        os.makedirs(extract_dir, exist_ok=True)
        extracted_files = []

        try:
            self._send_step(f"Extracting {installer_type} installer...")

            seven_z = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
            if seven_z:
                cmd = [seven_z, "x", "-y", f"-o{extract_dir}", installer_path]
                
                filters = [
                    "*.exe", "*.dll", "*.msi",
                    "*.json", "*.xml", "*.config", "*.manifest", "*.ini",
                    "*.js", "*.vdf",
                    "*.reg"
                ]
                
                for f in filters:
                    cmd.append(f"-i!{f}")
                    cmd.append(f"-i!**/{f}")
                
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                if result.returncode != 0:
                    try:
                        patoolib.extract_archive(installer_path, outdir=extract_dir, verbosity=-1)
                    except Exception:
                        raise Exception("Extraction not supported")
            else:
                try:
                    patoolib.extract_archive(installer_path, outdir=extract_dir, verbosity=-1)
                except Exception:
                    raise Exception("No extraction tool available")

            for pattern in ["**/*.exe", "**/*.dll"]:
                extracted_files.extend(glob(os.path.join(extract_dir, pattern), recursive=True))

            self._send_step(f"Found {len(extracted_files)} binaries in installer")

        except Exception as e:
            logging.warning(f"[Eagle] Extraction failed: {e}")
            self._send_step("Extraction skipped (not supported)")

        return extracted_files, extract_dir

    def _cleanup_extraction(self, extract_dir: str) -> None:
        """Clean up extracted files."""
        try:
            if extract_dir and os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
        except Exception as e:
            logging.warning(f"[Eagle] Cleanup failed: {e}")

    def analyze(self, executable_path: str) -> None:
        """Perform comprehensive PE analysis with YARA pattern matching."""
        self._send_step("Initialising Eagle...")
        basename = os.path.basename(executable_path)
        exe_dir = os.path.dirname(executable_path)
        self._send_step(f"Target: {basename}")

        extract_dir = None

        is_msi = basename.lower().endswith(".msi")
        if is_msi:
            self._send_step("MSI package detected - extracting for analysis...")

        try:
            if is_msi:
                insights = {
                    "Graphics": [], "Audio": [], "Runtimes": [], "Input": [],
                    "Social/DRM": [], "Engines": [], "Frameworks": [], "Protection": [],
                    "Packers": [], "Physics": [], "Media": [], "Crypto": [], "Upscaling": [],
                    "Installer": [{"name": "MSI", "source": "File Extension"}], "Warning": [], "Registry": [],
                    "Analysed Files": [basename],
                }
                metadata = {}
                
                extracted_files, extract_dir = self._extract_installer(executable_path, "MSI")
                if extracted_files:
                    settings = Gio.Settings.new("com.usebottles.bottles")
                    scan_limit = settings.get_int("eagle-scan-limit")
                    files_to_scan = extracted_files[:scan_limit]
                    for i, ef in enumerate(files_to_scan):
                        if not os.path.exists(ef):
                            continue
                        fname = os.path.basename(ef)
                        self._send_step(f"[{i+1}/{len(files_to_scan)}] Scanning: {fname}", delay=False)
                        self._scan_yara(ef, insights, source=fname)
                
                results = {
                    "name": basename,
                    "product_name": basename.rsplit(".", 1)[0],
                    "publisher": "Unknown",
                    "arch": "Unknown",
                    "min_os": "Unknown",
                    "admin": False,
                    "frameworks": [],
                    "suggestions": [],
                    "details": insights,
                    "metadata": metadata,
                }
                self._send_step("MSI analysis complete.")
                SignalManager.send(Signals.EagleFinished, Result(status=True, data=results))
                return

            self._send_step("Loading PE structure (Could take a while)...")
            pe = pefile.PE(executable_path, fast_load=False)

            insights = {
                "Graphics": [], "Audio": [], "Runtimes": [], "Input": [],
                "Social/DRM": [], "Engines": [], "Frameworks": [], "Protection": [],
                "Packers": [], "Physics": [], "Media": [], "Crypto": [], "Upscaling": [],
                "Installer": [], "Warning": [], "Registry": [],
                "Analysed Files": [basename],
            }
            metadata = {
                "compiler": None, "build_date": None, "is_packed": False, "packer": None,
                "large_address_aware": False, "dep_enabled": False, "aslr_enabled": False,
                "is_debug": False,
            }

            self._send_step("Detecting architecture...")
            arch = {0x14C: "x86 (32-bit)", 0x8664: "x86_64 (64-bit)", 0xAA64: "ARM64"}.get(
                pe.FILE_HEADER.Machine, "Unknown"
            )
            self._send_step(f"Architecture: {arch}")

            if arch == "ARM64":
                insights["Warning"].append({
                    "name": "ARM64 binary",
                    "description": "NOT SUPPORTED in Wine",
                    "severity": "critical",
                    "source": "Main Executable"
                })
                self._send_step("[!] WARNING: ARM64 binary will not work in Wine")

            self._send_step("Checking PE characteristics...")
            char = pe.FILE_HEADER.Characteristics
            metadata["large_address_aware"] = bool(char & 0x0020)
            if metadata["large_address_aware"] and "32" in arch:
                self._send_step("[+] Large Address Aware (can use >2GB RAM)")

            dll_char = pe.OPTIONAL_HEADER.DllCharacteristics
            metadata["dep_enabled"] = bool(dll_char & 0x0100)
            metadata["aslr_enabled"] = bool(dll_char & 0x0040)
            metadata["is_debug"] = bool(char & 0x0200)

            self._send_step("Checking OS requirements...")
            min_os = f"{pe.OPTIONAL_HEADER.MajorOperatingSystemVersion}.{pe.OPTIONAL_HEADER.MinorOperatingSystemVersion}"
            os_names = {"5.1": "Windows XP", "6.0": "Vista", "6.1": "Windows 7",
                        "6.2": "Windows 8", "6.3": "Windows 8.1", "10.0": "Windows 10/11"}
            os_name = os_names.get(min_os, f"Windows {min_os}")
            self._send_step(f"Minimum OS: {os_name}")

            self._send_step("Reading build metadata...")
            try:
                ts = pe.FILE_HEADER.TimeDateStamp
                if 0 < ts < 2147483647:
                    build_date = datetime.datetime.fromtimestamp(ts)
                    if 1990 < build_date.year < 2100:
                        metadata["build_date"] = build_date.strftime("%Y-%m-%d")
                        self._send_step(f"Build date: {metadata['build_date']}")
            except:
                pass

            self._send_step("Analysing Rich header...")
            try:
                if hasattr(pe, 'RICH_HEADER') and pe.RICH_HEADER:
                    for entry in pe.RICH_HEADER.values:
                        if entry['prodid'] in self.VS_PRODUCTS:
                            metadata["compiler"] = self.VS_PRODUCTS[entry['prodid']]
                            self._send_step(f"Compiler: {metadata['compiler']}")
                            break
            except:
                pass

            self._send_step("Scanning PE sections...")
            for section in pe.sections:
                try:
                    name = section.Name.decode('utf-8', errors='ignore').strip('\x00')
                    if name in self.PACKER_SECTIONS:
                        metadata["is_packed"] = True
                        metadata["packer"] = self.PACKER_SECTIONS[name]
                        self._send_step(f"[!] Packer detected: {metadata['packer']}")
                        break
                except:
                    continue

            self._send_step("Extracting version info...")
            publisher = "Unknown"
            product_name = basename
            try:
                if hasattr(pe, 'FileInfo') and pe.FileInfo:
                    for fi in pe.FileInfo[0]:
                        if hasattr(fi, 'Key') and fi.Key.decode() == 'StringFileInfo':
                            for st in fi.StringTable:
                                for k, v in st.entries.items():
                                    if k.decode() == 'CompanyName' and v.decode():
                                        publisher = v.decode()
                                    elif k.decode() == 'ProductName' and v.decode():
                                        product_name = v.decode()
                if publisher != "Unknown":
                    self._send_step(f"Publisher: {publisher}")
            except:
                pass

            self._send_step("Parsing application manifest...")
            admin_required = False
            dpi_aware = False
            try:
                if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
                    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                        if hasattr(entry, 'name') and entry.name == pefile.RESOURCE_TYPE.get('RT_MANIFEST'):
                            for me in entry.directory.entries:
                                data = pe.get_data(
                                    me.directory.entries[0].data.struct.OffsetToData,
                                    me.directory.entries[0].data.struct.Size
                                )
                                xml = data.decode('utf-8', errors='ignore')
                                if 'requireAdministrator' in xml:
                                    admin_required = True
                                    self._send_step("[!] Requires administrator")
                                if 'dpiAware' in xml.lower():
                                    dpi_aware = True
            except:
                pass

            self._send_step("Checking .NET CLR header...")
            is_net = False
            try:
                clr = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR']]
                if clr.VirtualAddress != 0 and clr.Size > 0:
                    is_net = True
                    self._send_step("[✓] .NET managed code detected")
            except:
                pass

            self._send_step("Analysing import table...")
            imports = set()
            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    imports.add(entry.dll.decode('utf-8', errors='ignore').lower())

            try:
                if hasattr(pe, 'DIRECTORY_ENTRY_DELAY_IMPORT'):
                    for entry in pe.DIRECTORY_ENTRY_DELAY_IMPORT:
                        imports.add(entry.dll.decode('utf-8', errors='ignore').lower())
            except:
                pass

            self._send_step(f"Found {len(imports)} imported libraries")

            self._send_step("Mapping dependencies...")
            for dll in imports:
                if dll in self.DLL_MAPPINGS:
                    name, cat = self.DLL_MAPPINGS[dll]
                    existing_names = [i['name'] for i in insights.get(cat, [])]
                    if name not in existing_names:
                        insights[cat].append({
                            "name": name,
                            "source": "Imports"
                        })
                        self._send_step(f"[{cat}] {name} (Import)", delay=False)

            time.sleep(STEP_DELAY)

            if is_net:
                existing_runtimes = [i['name'] for i in insights["Runtimes"]]
                if "hostfxr.dll" in imports or "coreclr.dll" in imports:
                    if ".NET Core/5+" not in existing_runtimes:
                        insights["Runtimes"].append({"name": ".NET Core/5+", "source": "CLR Header"})
                elif ".NET Framework" not in existing_runtimes:
                    insights["Runtimes"].append({"name": ".NET Framework", "source": "CLR Header"})

            self._send_step("Deep pattern scanning (YARA)...")
            yara_matches = self._scan_yara(executable_path, insights)
            if yara_matches:
                self._send_step(f"YARA: {len(yara_matches)} patterns matched")

            self._send_step("Scanning directory structure...")

            exe_base = basename.rsplit(".", 1)[0]
            runtimeconfig = f"{exe_base}.runtimeconfig.json"
            deps_json = f"{exe_base}.deps.json"
            net_marker_dirs = [exe_dir, os.path.join(exe_dir, "bin")]
            for check_dir in net_marker_dirs:
                if os.path.exists(os.path.join(check_dir, runtimeconfig)):
                    insights["Analysed Files"].append(runtimeconfig)
                    if ".NET Core/5+" not in insights["Runtimes"]:
                        insights["Runtimes"].append(".NET Core/5+")
                        self._send_step("[Runtimes] .NET Core/5+ (self-contained)")
                    break
                elif os.path.exists(os.path.join(check_dir, deps_json)):
                    insights["Analysed Files"].append(deps_json)
                    if ".NET Core/5+" not in insights["Runtimes"]:
                        insights["Runtimes"].append(".NET Core/5+")
                        self._send_step("[Runtimes] .NET Core/5+ (self-contained)")
                    break

            if os.path.exists(os.path.join(exe_dir, "Engine")) or \
               os.path.exists(os.path.join(exe_dir, "../Engine/Binaries")):
                if "Unreal" not in insights["Engines"]:
                    insights["Engines"].append("Unreal")
                    self._send_step("[Engines] Unreal Engine")

            if os.path.exists(os.path.join(exe_dir, "renpy")):
                if "Ren'Py" not in insights["Engines"]:
                    insights["Engines"].append("Ren'Py")
                    self._send_step("[Engines] Ren'Py")

            if os.path.exists(os.path.join(exe_dir, "www")) or \
               os.path.exists(os.path.join(exe_dir, "Game.rgss3a")):
                if "RPG Maker" not in insights["Engines"]:
                    insights["Engines"].append("RPG Maker")
                    self._send_step("[Engines] RPG Maker")

            pck = os.path.join(exe_dir, f"{basename.rsplit('.', 1)[0]}.pck")
            if os.path.exists(pck):
                insights["Analysed Files"].append(os.path.basename(pck))
                if "Godot" not in insights["Engines"]:
                    insights["Engines"].append("Godot")
                    self._send_step("[Engines] Godot")

            if os.path.exists(os.path.join(exe_dir, "resources/app.asar")):
                asar_path = os.path.join(exe_dir, "resources/app.asar")
                insights["Analysed Files"].append("resources/app.asar")
                if "Electron" not in insights["Frameworks"]:
                    insights["Frameworks"].append("Electron")
                    self._send_step("[Frameworks] Electron")
                
                # Extract and scan ASAR
                self._send_step("Analysing Electron archive...")
                extracted_asar_files, asar_extract_dir = self._extract_asar(asar_path)
                if extracted_asar_files:
                    settings = Gio.Settings.new("com.usebottles.bottles")
                    scan_limit = settings.get_int("eagle-scan-limit")
                    for i, ef in enumerate(extracted_asar_files[:scan_limit]):
                        fname = os.path.basename(ef)
                        self._send_step(f"Scanning ASAR content: {fname}", delay=False)
                        self._scan_yara(ef, insights, source=f"Electron Source: {fname}")
                    
                    self._cleanup_extraction(asar_extract_dir)

            # Deep Scan for Neighbor Files
            self._send_step("Scanning neighbor files...")
            neighbor_files = []

            if self._is_safe_neighbor_dir(exe_dir):
                try:
                    root_files = os.listdir(exe_dir)
                    for f in root_files:
                        f_lower = f.lower()
                        if f_lower.endswith(".dll"):
                            neighbor_files.append(os.path.join(exe_dir, f))
                except:
                    pass
            else:
                self._send_step("Skipping neighbor scan (Common directory detected)")

            unity_data = os.path.join(exe_dir, f"{basename.rsplit('.', 1)[0]}_Data")
            if os.path.exists(unity_data):
                plugins_dir = os.path.join(unity_data, "Plugins")
                if os.path.exists(plugins_dir):
                    neighbor_files.extend(glob(os.path.join(plugins_dir, "**/*.dll"), recursive=True))

            scan_limit = 20 
            if neighbor_files:
                self._send_step(f"Found {len(neighbor_files)} neighbor files. Ensure directory is clean to avoid false positives.")
                insights["Warning"].append({
                    "name": "Mixed Files Risk",
                    "description": "Neighbor files were analyzed. Ensure all files in this directory belong to the same software to avoid false positives.",
                    "severity": "warning",
                    "source": "Context Scanner"
                })
            
            for i, nf in enumerate(neighbor_files[:scan_limit]):
                fname = os.path.basename(nf)
                # Avoid duplicates
                if fname not in insights["Analysed Files"] and nf != executable_path:
                    self._send_step(f"Scanning context: {fname}", delay=False)
                    self._scan_yara(nf, insights, source=f"Neighbor: {fname}")
                    try: 
                        f_lower = fname.lower()
                        if f_lower in self.DLL_MAPPINGS:
                             name, cat = self.DLL_MAPPINGS[f_lower]
                             existing_names = [x['name'] for x in insights.get(cat, [])]
                             if name not in existing_names:
                                 insights[cat].append({"name": name, "source": f"Neighbor: {fname}"})
                    except:
                        pass
                    insights["Analysed Files"].append(fname)

            extract_dir = None
            if insights["Installer"]:
                installer_item = insights["Installer"][0]
                installer_name = installer_item["name"] if isinstance(installer_item, dict) else str(installer_item)
                self._send_step(f"Installer detected ({installer_name}), performing deep scan...")
                try:
                    extracted_files, extract_dir = self._extract_installer(executable_path, installer_name)
                    if extracted_files:
                        exe_files = [f for f in extracted_files if f.lower().endswith(".exe")]
                        if exe_files:
                            main_exe = max(exe_files, key=os.path.getsize)
                            self._send_step(f"Scanning main binary: {os.path.basename(main_exe)}")

                            settings = Gio.Settings.new("com.usebottles.bottles")
                            scan_limit = settings.get_int("eagle-scan-limit")
                            files_to_scan = extracted_files[:scan_limit]
                            
                            for i, ef in enumerate(files_to_scan):
                                if not os.path.exists(ef):
                                    continue
                                fname = os.path.basename(ef)
                                insights["Analysed Files"].append(fname)
                                self._send_step(f"[{i+1}/{len(files_to_scan)}] Scanning: {fname}", delay=False)
                                self._scan_yara(ef, insights, source=fname)
                            
                except Exception as e:
                    logging.warning(f"[Eagle] Deep scan failed: {e}")
                    self._send_step(f"Deep scan failed, continuing with surface analysis")

            self._send_step("Generating optimisation suggestions...")
            suggestions = []
            
            flat_insights = {
                k: [i["name"] if isinstance(i, dict) else i for i in v]
                for k, v in insights.items()
            }

            dx = [v for v in flat_insights.get("Graphics", []) if "DirectX" in v or "D3D" in v or "DXGI" in v]
            has_dx12 = any("12" in v for v in dx)
            has_dx11 = any("11" in v or "9" in v or "10" in v or "DXGI" in v for v in dx)
            has_vulkan = "Vulkan" in flat_insights.get("Graphics", [])

            dx_engines = ["Unity", "Unity IL2CPP", "Unreal", "Godot", "CryEngine", "REDengine", "Source", "RPG Maker"]
            has_dx_engine = any(e in flat_insights.get("Engines", []) for e in dx_engines)

            dx12_engines = ["Unreal", "REDengine"]
            has_dx12_engine = any(e in flat_insights.get("Engines", []) for e in dx12_engines)

            if has_dx12 or has_dx12_engine:
                suggestions.append({"key": "vkd3d", "value": True, "label": "Enable VKD3D (DX12)"})
            if has_dx11 or (has_dx_engine and not has_vulkan):
                suggestions.append({"key": "dxvk", "value": True, "label": "Enable DXVK (DX9-11)"})
            if has_vulkan and not has_dx_engine:
                suggestions.append({"key": "dxvk", "value": False, "label": "DXVK not needed (native Vulkan)"})

            if "NVAPI" in flat_insights.get("Graphics", []):
                suggestions.append({"key": "dxvk_nvapi", "value": True, "label": "Enable DXVK-NVAPI"})

            # Upscaling Technologies
            upscaling = flat_insights.get("Upscaling", [])
            if "DLSS" in upscaling or "DLSS 3 Frame Gen" in upscaling:
                suggestions.append({"key": "dxvk_nvapi", "value": True, "label": "Enable DXVK-NVAPI (for DLSS)"})
            if "AMD FSR" in upscaling or "AMD FSR 2" in upscaling:
                suggestions.append({"key": "fsr", "value": True, "label": "Enable FSR (native support detected)"})

            if flat_insights.get("Engines", []) or flat_insights.get("Graphics", []):
                suggestions.append({"key": "gamemode", "value": True, "label": "Enable GameMode"})
                suggestions.append({"key": "discrete_gpu", "value": True, "label": "Use discrete GPU"})
                suggestions.append({"key": "sync", "value": "esync", "label": "Esync (threading)"})

            has_physx = "PhysX" in flat_insights.get("Physics", [])
            if has_dx11 or has_vulkan or has_physx:
                lfx_enabled = has_physx
                suggestions.append({"key": "latencyflex", "value": lfx_enabled, "label": "LatencyFlex (input lag)"})


            # .NET & Mono
            net_runtimes = [r for r in flat_insights.get("Runtimes", []) if ".NET" in r]
            has_mono = "Mono" in flat_insights.get("Runtimes", [])
            
            if is_net and not net_runtimes:
                net_runtimes.append(".NET Framework")
            
            if has_mono and net_runtimes:
                 # Both detected: recommend Mono first
                 suggestions.append({"key": "dep_mono", "value": False, "label": "Wine Mono (Recommended first)"})
                 for rt in set(net_runtimes):
                     suggestions.append({"key": "dep_dotnet", "value": False, "label": f"{rt} (Try Mono first)"})
            else:
                 # Standard behavior
                 for rt in set(net_runtimes):
                     suggestions.append({"key": "dep_dotnet", "value": False, "label": rt})
                 if has_mono and not net_runtimes:
                      suggestions.append({"key": "dep_mono", "value": False, "label": "Wine Mono"})

            vcpp = [r for r in flat_insights.get("Runtimes", []) if "VC++" in r]
            if vcpp:
                suggestions.append({"key": "dep_vcredist", "value": False, "label": f"Visual C++ ({', '.join(set(vcpp))})"})

            if not dpi_aware:
                suggestions.append({"key": "virtual_desktop", "value": False, "label": "Virtual Desktop (DPI)"})

            messages = []

            # Generalized patrns and hints
            warns = flat_insights.get("Warning", [])
            frames = flat_insights.get("Frameworks", [])

            if "UWP/Modern API" in warns:
                messages.append({
                    "name": "UWP/Modern App",
                    "description": "Set Windows Version to 'Windows 10' or '11' and extract 'WinMetadata' to system32.",
                    "severity": "high",
                    "context": ["Detected Modern Windows API usage"]
                })

            if "WPF" in frames:
                messages.append({
                    "name": "WPF Optimization",
                    "description": "Use a runner with 'ChildWindow' patches (e.g. Soda, Wine-GE-Custom, Proton-GE).",
                    "severity": "info",
                    "context": ["Detected WPF (Windows Presentation Foundation)"]
                })

            # INFO Messages
            if metadata["is_packed"]:
                messages.append({
                    "name": "Packed Binary",
                    "description": "Analysis might be limited due to packing.",
                    "severity": "info",
                    "context": [f"Packed with {metadata['packer']}"]
                })
            
            if flat_insights.get("Protection", []):
                prots = ", ".join(flat_insights.get("Protection", []))
                messages.append({
                    "name": "Protection Software",
                    "description": "This might cause compatibility or performance issues.",
                    "severity": "high",
                    "context": [f"Detected: {prots}"]
                })

            upscaling = flat_insights.get("Upscaling", [])
            if "Intel XeSS" in upscaling:
                messages.append({
                    "name": "Intel XeSS",
                    "description": "You might need to install the XeSS runtime manually.",
                    "severity": "info",
                    "context": ["Detected XeSS libraries"]
                })

            frameworks = []
            for cat, items in insights.items():
                for item in items:
                    frameworks.append(f"{cat}: {item}")

            if not any(insights.values()):
                self._send_step("No specific frameworks detected")

            results = {
                "name": basename,
                "product_name": product_name,
                "publisher": publisher,
                "arch": arch,
                "min_os": os_name,
                "admin": admin_required,
                "frameworks": frameworks,
                "suggestions": suggestions,
                "messages": messages,
                "details": insights,
                "metadata": metadata,
            }

            self._send_step("Analysis complete.")
            SignalManager.send(Signals.EagleFinished, Result(status=True, data=results))

        except Exception as e:
            self._send_step(f"Error: {str(e)}")
            logging.error(f"[Eagle] {str(e)}")
            SignalManager.send(Signals.EagleFinished, Result(status=False, data={"error": str(e)}))
        finally:
            if extract_dir:
                self._cleanup_extraction(extract_dir)
