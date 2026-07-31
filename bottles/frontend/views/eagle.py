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
import uuid
import webbrowser
from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import SignalManager, Signals
from bottles.backend.utils.threading import RunAsync
from bottles.backend.managers.eagle import EagleManager
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.executor import WineExecutor
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.windows.generic import SourceDialog


@Gtk.Template(resource_path="/com/usebottles/bottles/eagle.ui")
class EagleView(Gtk.Box):
    __gtype_name__ = "EagleView"

    stack = Gtk.Template.Child()
    banner_disclaimer = Gtk.Template.Child()
    scrolled_steps = Gtk.Template.Child()
    steps_list = Gtk.Template.Child()
    list_suggestions = Gtk.Template.Child()
    group_results = Gtk.Template.Child()
    group_warnings = Gtk.Template.Child()
    group_files = Gtk.Template.Child()
    label_files = Gtk.Template.Child()
    list_dependencies = Gtk.Template.Child()
    group_dependencies = Gtk.Template.Child()
    list_warnings = Gtk.Template.Child()
    btn_launch = Gtk.Template.Child()
    btn_report = Gtk.Template.Child()
    group_donate = Gtk.Template.Child()
    btn_eagle_donate = Gtk.Template.Child()

    def __init__(self, details, config: BottleConfig, **kwargs):
        super().__init__(**kwargs)
        self.details = details
        self.config = config
        self.manager = EagleManager(config)
        self.analysis_results = None
        self.target_path = None
        self._analysis_steps: list[Adw.ActionRow] = []
        self._files_rows: list[Adw.ActionRow] = []
        self._results_rows: list[Adw.ActionRow] = []

        self.btn_launch.connect("clicked", self.__on_launch_clicked)
        self.btn_report.connect("clicked", self.__on_report_clicked)
        self.btn_eagle_donate.connect("clicked", self.__on_donate_clicked)
        
        SignalManager.connect(Signals.EagleStep, self.__on_eagle_step)
        SignalManager.connect(Signals.EagleFinished, self.__on_eagle_finished)

    def analyze(self, executable_path: str) -> None:
        """
        Starts the analysis process on the given executable path.
        """
        self.target_path = executable_path
        self.analysis_results = None
        
        self.stack.set_visible_child_name("console")
        self.banner_disclaimer.set_revealed(False)
        self.group_warnings.set_visible(False)
        self.group_files.set_visible(False)
        self.group_dependencies.set_visible(False)
        self.btn_report.set_visible(False)
        self.btn_launch.set_visible(False)
        self.group_results.set_visible(False)
        self.group_donate.set_visible(False)

        if self._analysis_steps:
             self._analysis_steps.clear()
        
        self.__reset_steps()
        
        # Clear all dynamic lists/groups
        while row := self.list_suggestions.get_first_child():
            self.list_suggestions.remove(row)
        while row := self.list_warnings.get_first_child():
            self.list_warnings.remove(row)
        while row := self.list_dependencies.get_first_child():
            self.list_dependencies.remove(row)
            
        # Reset label_files rows
        if self._files_rows:
             for row in self._files_rows:
                 try: self.label_files.remove(row)
                 except: pass
             self._files_rows.clear()
        
        # Reset group_results using tracking list
        if self._results_rows:
            for row in self._results_rows:
                try: self.group_results.remove(row)
                except: pass
            self._results_rows.clear()

        def _analyze():
            self.manager.analyze(executable_path)

        RunAsync(_analyze)

    def __reset_steps(self) -> None:
        """
        Clear all step rows from the list.
        """
        self._analysis_steps.clear()
        child = self.steps_list.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.steps_list.remove(child)
            child = next_child

    def __create_step_row(self, text: str) -> Gtk.Box:
        """
        Create a compact step row with completion indicator.
        """
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(4)
        row.set_margin_bottom(4)

        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.set_ellipsize(3)
        label.add_css_class("dim-label")
        row.append(label)

        check_image = Gtk.Image.new_from_icon_name("selection-mode-symbolic")
        check_image.add_css_class("accent")
        check_image.set_visible(False)
        row.append(check_image)

        row._completion_icon = check_image
        row._label = label

        return row

    def __mark_last_step_completed(self) -> None:
        """
        Mark the last step as completed with checkmark.
        """
        if not self._analysis_steps:
            return
        self.__set_step_completed(self._analysis_steps[-1])

    def __set_step_completed(self, row: Adw.ActionRow) -> None:
        """
        Show the completion icon for a step.
        """
        icon = getattr(row, "_completion_icon", None)
        if icon:
            icon.set_visible(True)

    @GtkUtils.run_in_main_loop
    def __on_eagle_step(self, res: Result) -> None:
        msg = res.data
        if not msg or not msg.strip():
            return

        self.__mark_last_step_completed()

        row = self.__create_step_row(msg.strip())
        self.steps_list.append(row)
        self._analysis_steps.append(row)

        def _scroll_to_bottom():
            adj = self.scrolled_steps.get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())
            return False

        GLib.idle_add(_scroll_to_bottom)
    
    def __create_info_row(self, title: str, subtitle: str, icon: str = None) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(title)
        row.set_subtitle(subtitle)
        if icon:
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))
        return row

    @GtkUtils.run_in_main_loop
    def __on_eagle_finished(self, res: Result) -> None:
        self.__mark_last_step_completed()

        self.analysis_results = res.data
        data = self.analysis_results
        details = data.get("details", {})
        
        self.group_results.set_visible(True)
        self.group_donate.set_visible(True)

        # Clear existing rows
        if self._results_rows:
            for row in self._results_rows:
                try: self.group_results.remove(row)
                except: pass
            self._results_rows.clear()
            
        def _add_result(row):
            self.group_results.add(row)
            self._results_rows.append(row)

        _add_result(self.__create_info_row(
            _("Product Name"), 
            data.get("product_name", "Unknown"), 
            "package-x-generic-symbolic"
        ))
        _add_result(self.__create_info_row(
            _("Publisher"), 
            data.get("publisher", "Unknown"), 
            "avatar-default-symbolic"
        ))
        _add_result(self.__create_info_row(
            _("Architecture"), 
            data.get("arch", "Unknown"), 
            "emblem-system-symbolic"
        ))
        _add_result(self.__create_info_row(
            _("Minimum OS Version"), 
            data.get("min_os", "Unknown"), 
            "software-update-available-symbolic"
        ))
        _add_result(self.__create_info_row(
            _("Needs Administrator"), 
            _("Yes") if data.get("admin") else _("No"), 
            "dialog-password-symbolic"
        ))

        metadata = data.get("metadata", {})
        
        if metadata.get("compiler"):
            _add_result(self.__create_info_row(
                _("Compiler"), 
                metadata["compiler"], 
                "applications-engineering-symbolic"
            ))

        if metadata.get("build_date"):
            _add_result(self.__create_info_row(
                _("Build Date"), 
                metadata["build_date"], 
                "x-office-calendar-symbolic"
            ))

        intel = data.get("intel")
        if intel:
            row = Adw.ExpanderRow()
            row.set_title(_("Eagle Intelligence"))
            if intel.get("source") == "winetricks":
                row.set_subtitle(
                    _("{0}, recognized from curated application metadata").format(
                        intel["name"],
                    )
                )
            else:
                row.set_subtitle(
                    _("{0}, compatibility signals from {1} community reports").format(
                        intel["name"], intel["reports"]
                    )
                )
            intel_icon = Gtk.Image.new_from_icon_name("network-transmit-receive-symbolic")
            row.add_prefix(intel_icon)

            badges = Gtk.Box(spacing=6)
            source_badge = Gtk.Label(label=intel["source"].upper())
            source_badge.set_valign(Gtk.Align.CENTER)
            source_badge.add_css_class("tag")
            source_badge.add_css_class("caption")
            source_badge.add_css_class("accent")
            badges.append(source_badge)
            if intel.get("tier"):
                tier_badge = Gtk.Label(label=intel["tier"].upper())
                tier_badge.set_valign(Gtk.Align.CENTER)
                tier_badge.add_css_class("tag")
                tier_badge.add_css_class("caption")
                tier_badge.add_css_class(f"grade-{intel['tier'].title()}")
                badges.append(tier_badge)
            row.add_suffix(badges)

            def _add_intel_row(title, subtitle, icon_name, suffix=None):
                intel_row = Adw.ActionRow()
                intel_row.set_title(title)
                intel_row.set_subtitle(subtitle)
                intel_row.set_subtitle_lines(0)
                intel_row.add_prefix(Gtk.Image.new_from_icon_name(icon_name))
                if suffix is not None:
                    intel_row.add_suffix(suffix)
                intel_row.add_css_class("property")
                row.add_row(intel_row)

            match_labels = {
                "sha256": _("Exact binary hash match"),
                "imphash": _("Import hash match"),
                "steam_appid": _("Steam installation match"),
                "name": _("Exact application name"),
                "fuzzy": _("Probable application name"),
            }
            _add_intel_row(
                _("Match confidence"),
                match_labels.get(intel["match"], intel["match"]),
                "system-search-symbolic",
            )

            if intel.get("source") != "winetricks":
                verdict_total = intel["verdict_yes"] + intel["verdict_no"]
                positive_ratio = (
                    intel["verdict_yes"] / verdict_total if verdict_total else 0
                )
                score = Gtk.LevelBar.new_for_interval(0, 1)
                score.set_value(positive_ratio)
                score.set_size_request(110, -1)
                score.set_valign(Gtk.Align.CENTER)
                score.set_tooltip_text(
                    _("{0}% positive verdicts").format(round(positive_ratio * 100))
                )
                score.add_css_class("intel-score")
                _add_intel_row(
                    _("Community verdict"),
                    _("{0} positive / {1} negative reports").format(
                        intel["verdict_yes"],
                        intel["verdict_no"],
                    ),
                    "selection-mode-symbolic",
                    score,
                )
            for name, info in intel.get("env", {}).items():
                _add_intel_row(
                    _("Environment Variable"),
                    f"{name}={info['value']} (x{info['evidence']})",
                    "utilities-terminal-symbolic",
                )
            for dll, info in intel.get("dll_overrides", {}).items():
                _add_intel_row(
                    _("DLL Override"),
                    f"{dll}={info['value']} (x{info['evidence']})",
                    "application-x-addon-symbolic",
                )
            for argument in intel.get("args", []):
                _add_intel_row(
                    _("Launch Argument"),
                    f"{argument['value']} (x{argument['evidence']})",
                    "system-run-symbolic",
                )
            for note in intel.get("notes", []):
                _add_intel_row(
                    _("Evidence note"),
                    note,
                    "dialog-information-symbolic",
                )

            for attribution in intel.get("attributions", []):
                source_button = self.__intel_link_button(
                    attribution["url"],
                    _("Open {0} data source").format(attribution["name"]),
                )
                _add_intel_row(
                    _("Source: {0}").format(attribution["name"]),
                    attribution["dataset"],
                    "text-x-generic-symbolic",
                    source_button,
                )
                for license_info in attribution["licenses"]:
                    license_button = self.__intel_link_button(
                        license_info["url"],
                        _("Open {0} license").format(license_info["name"]),
                    )
                    _add_intel_row(
                        _("Data license"),
                        _("{0}: {1}").format(
                            attribution["name"],
                            license_info["name"],
                        ),
                        "dialog-password-symbolic",
                        license_button,
                    )
            if intel.get("source") == "protondb":
                _add_intel_row(
                    _("Rating method"),
                    _("The tier is calculated by Eagle Intel, not by ProtonDB."),
                    "applications-science-symbolic",
                )
            _add_result(row)

        # Category mapping for detected technologies
        CATEGORY_META = {
            "Graphics": {"title": _("Graphics API"), "icon": "video-display-symbolic"},
            "Audio": {"title": _("Audio Engine"), "icon": "audio-x-generic-symbolic"},
            "Runtimes": {"title": _("Runtimes and Libraries"), "icon": "library-symbolic"},
            "Social/DRM": {"title": _("Social and DRM"), "icon": "network-workgroup-symbolic"},
            "Input": {"title": _("Input"), "icon": "input-gaming-symbolic"},
            "Protection": {"title": _("Protection"), "icon": "security-high-symbolic"},
            "Upscaling": {"title": _("Upscaling Technology"), "icon": "video-display-symbolic"},
            "Physics": {"title": _("Physics Engine"), "icon": "emblem-system-symbolic"},
            "Media": {"title": _("Media Playback"), "icon": "video-x-generic-symbolic"},
            "Crypto": {"title": _("Crypto and Hashing"), "icon": "security-low-symbolic"},
            "Frameworks": {"title": _("Engines and Frameworks"), "icon": "applications-engineering-symbolic"},
            "System": {"title": _("System Interaction"), "icon": "utilities-terminal-symbolic"},
            "Installer": {"title": _("Installer Type"), "icon": "system-software-install-symbolic"},
            "Registry": {"title": _("Registry"), "icon": "preferences-system-symbolic"},
        }

        # Analysed Files
        analysed_files = details.get("Analysed Files", [])
        if analysed_files:
            self.group_files.set_visible(True)
            
            if not hasattr(self, "_files_rows"):
                self._files_rows = []
                
            for fname in analysed_files:
                row = Adw.ActionRow()
                row.set_title(fname)
                row.add_css_class("property")
                self.label_files.add_row(row)
                self._files_rows.append(row)
        else:
            self.group_files.set_visible(False)

        # Merge Engines into Frameworks for display
        engines = details.get("Engines", [])
        if engines:
            if "Frameworks" not in details:
                 details["Frameworks"] = []
            existing = [f["name"] if isinstance(f, dict) else f for f in details["Frameworks"]]
            for e in engines:
                e_name = e["name"] if isinstance(e, dict) else e
                if e_name not in existing:
                    details["Frameworks"].append(e)

        # Iterate and Populate
        for key, meta in CATEGORY_META.items():
            items = details.get(key, [])
            if not items:
                continue

            title = meta["title"]
            icon = meta["icon"]
            final_items = []
            for item in items:
                if isinstance(item, dict):
                    name = item.get("name", "Unknown")
                    source = item.get("source", "")
                    context = item.get("context", [])
                    
                    if key in ["System", "Registry"] and context and isinstance(context, list):
                        # For these categories, expand context into items
                        for ctx_item in context:
                            entry = {
                                "title": ctx_item,
                                "subtitle": f"{name} ({source})" if source else name
                            }
                            final_items.append(entry)
                    else:
                         # Standard item
                        subtitle_sys = source
                        context_str = ""
                        if context:
                             context_str = ", ".join(context[:3]) + ("..." if len(context)>3 else "")
                        
                        full_sub = ""
                        if subtitle_sys: full_sub += f"{subtitle_sys}"
                        if context_str: full_sub += f" · {context_str}" if full_sub else context_str
                        
                        final_items.append({"title": name, "subtitle": full_sub})
                else:
                    final_items.append({"title": str(item), "subtitle": ""})

            count = len(final_items)
            if count == 0:
                continue

            if count == 1:
                # Single item, then using ActionRow
                item = final_items[0]
                row = Adw.ActionRow()
                row.set_title(title)
                row.set_subtitle(f"{item['title']}")
                if item['subtitle']:
                     sub = item['title']
                     if item.get("subtitle"):
                         sub += f" ({item['subtitle']})"
                     row.set_subtitle(sub)
                
                row.add_prefix(Gtk.Image.new_from_icon_name(icon))
                _add_result(row)
            
            else:
                # Multiple items, then using ExpanderRow
                row = Adw.ExpanderRow()
                row.set_title(title)
                row.set_subtitle(_("{0} detected").format(count))
                row.add_prefix(Gtk.Image.new_from_icon_name(icon))
                
                for item in final_items:
                    sub_row = Adw.ActionRow()
                    sub_row.set_title(item['title'])
                    if item.get('subtitle'):
                        sub_row.set_subtitle(item['subtitle'])
                    sub_row.add_css_class("property")
                    row.add_row(sub_row)
                
                _add_result(row)

        while child := self.list_warnings.get_first_child():
            self.list_warnings.remove(child)

        warnings = details.get("Warning", [])
        messages = data.get("messages", [])

        system_items = details.get("System", [])
        system_alerts = [item for item in system_items if isinstance(item, dict) and item.get("severity") in ["high", "critical"]]

        # security findings (malware/stealer patterns) are surfaced as alerts
        security_alerts = details.get("Security", [])

        all_alerts = security_alerts + warnings + messages + system_alerts

        if all_alerts:
            self.group_warnings.set_visible(True)
            self.group_warnings.set_title(_("Analysis Insights"))
            
            for item in all_alerts:
                row = Adw.ActionRow()
                icon_name = "dialog-information-symbolic"
                
                if isinstance(item, dict):
                    name = item.get("name", "Unknown")
                    description = item.get("description", "")
                    context = item.get("context", [])
                    source = item.get("source", "")
                    is_ue_bootstrapper = (name == "Unreal Engine Bootstrapper")

                    details_list = []
                    if source and source != "Main Executable":
                        details_list.append(f"Source: {source}")
                    
                    if context and not is_ue_bootstrapper:
                        ctx_str = ", ".join(context[:5])
                        if len(context) > 5:
                            ctx_str += "..."
                        details_list.append(f"Detected: {ctx_str}")
                    
                    if details_list:
                        description += "\n" + "\n".join(details_list)

                    row.set_title(name)
                    row.set_subtitle(description)
                    row.set_subtitle_lines(0)

                    severity = item.get("severity", "info")
                    if severity == "critical":
                        row.add_css_class("error")
                        icon_name = "dialog-error-symbolic"
                    elif severity == "high":
                        row.add_css_class("warning")
                        icon_name = "dialog-warning-symbolic"

                    if "Protection" in name:
                        icon_name = "security-high-symbolic"
                    elif "Packed" in name:
                         icon_name = "package-x-generic-symbolic"
                    elif "Optimization" in name or "WPF" in name:
                         icon_name = "emblem-system-symbolic"
                    elif "XeSS" in name or "DLSS" in name or "FSR" in name:
                         icon_name = "video-display-symbolic"
                    elif "UWP" in name:
                         icon_name = "applications-system-symbolic"
                else:
                    text = str(item)
                    row.set_title(text)
                    if "Protection" in text:
                        icon_name = "security-high-symbolic"
                    elif "Packed" in text:
                         icon_name = "package-x-generic-symbolic"
                    elif "Warning" in text:
                         row.add_css_class("warning")
                         icon_name = "dialog-warning-symbolic"

                icon = Gtk.Image.new_from_icon_name(icon_name)
                row.add_prefix(icon)
                self.list_warnings.append(row)

                if isinstance(item, dict) and is_ue_bootstrapper and context:
                    shipping_path = context[0]
                    switch_row = Adw.SwitchRow()
                    switch_row.set_title(_("Use shipping binary instead"))
                    switch_row.set_subtitle(os.path.basename(shipping_path))
                    switch_row._ue_shipping_exe = shipping_path
                    self.list_warnings.append(switch_row)
        else:
            self.group_warnings.set_visible(False)

        child = self.list_suggestions.get_first_child()
        while child:
            self.list_suggestions.remove(child)
            child = self.list_suggestions.get_first_child()
            
        child = self.list_dependencies.get_first_child()
        while child:
            self.list_dependencies.remove(child)
            child = self.list_dependencies.get_first_child()

        suggestions = data.get("suggestions", [])
        has_opts = False
        has_deps = False
        
        for item in suggestions:
            key = item.get("key", "")
            label = item.get("label", "")
            
            if key.startswith("dep_"):
                row = Adw.ActionRow()
                row.set_title(label)
                row.add_prefix(Gtk.Image.new_from_icon_name("package-x-generic-symbolic"))
                self.list_dependencies.append(row)
                has_deps = True
            else:
                row = Adw.SwitchRow()
                row.set_title(label)
                row.set_subtitle(_("Apply this recommendation"))
                row.set_active(item.get("apply", bool(item.get("value", False))))
                row.suggestion_key = key
                row.suggestion_value = item.get("value", False)
                component_names = {
                    "dxvk": "DXVK",
                    "vkd3d": "VKD3D",
                    "dxvk_nvapi": "DXVK-NVAPI",
                }
                if (
                    key in component_names
                    and item.get("value") is True
                    and not self.config.Parameters[key]
                ):
                    row.set_active(False)
                    row.set_sensitive(False)
                    row.set_subtitle(
                        _("Enable {0} for this bottle first").format(
                            component_names[key]
                        )
                    )
                self.list_suggestions.append(row)
                has_opts = True
        self.list_suggestions.get_parent().set_visible(has_opts)
        self.group_dependencies.set_visible(has_deps)

        self.stack.set_visible_child_name("results")
        self.banner_disclaimer.set_revealed(True)
        self.btn_launch.set_visible(True)
        self.btn_report.set_visible(True)

    def __on_launch_clicked(self, _widget) -> None:
        if not self.analysis_results or not self.target_path:
            return

        view_bottle = self.details.view_bottle
        config = view_bottle.config
        manager = view_bottle.manager

        overrides = {}
        environment = {}
        arguments = []
        dll_overrides = []
        row = self.list_suggestions.get_first_child()
        while row:
            key = getattr(row, "suggestion_key", None)
            if key and row.get_active():
                value = getattr(row, "suggestion_value", True)
                if key.startswith("intel_env:"):
                    environment[key.removeprefix("intel_env:")] = value
                elif key.startswith("intel_dll:"):
                    dll = key.removeprefix("intel_dll:")
                    dll_overrides.append(f"{dll}={value}")
                elif key.startswith("intel_arg:"):
                    arguments.append(value)
                else:
                    overrides[key] = value
            row = row.get_next_sibling()

        if dll_overrides:
            environment["WINEDLLOVERRIDES"] = ";".join(dll_overrides)

        path = self.target_path
        child = self.list_warnings.get_first_child()
        while child:
            if hasattr(child, "_ue_shipping_exe"):
                if child.get_active():
                    path = child._ue_shipping_exe
                break
            child = child.get_next_sibling()

        basename = os.path.basename(path)
        _uuid = str(uuid.uuid4())
        
        program = {
            "executable": basename,
            "name": basename.rsplit(".", 1)[0],
            "path": path,
            "id": _uuid,
            "folder": ManagerUtils.get_exe_parent_dir(config, path),
        }

        program.update(overrides)
        if environment:
            program["environment"] = environment
        if arguments:
            program["arguments"] = " ".join(arguments)
        
        config = manager.update_config(
            config=config,
            key=_uuid,
            value=program,
            scope="External_Programs",
            fallback=True,
        ).data["config"]
        
        view_bottle.config = config
        view_bottle.update_programs(config=config, force_add=program)
        
        self.details.window.show_toast(_('"{0}" added').format(program["name"]))
        
        def _run():
            WineExecutor.run_program(config, program, False)
            return True

        def _callback(_result, _error):
            pass

        RunAsync(_run, callback=_callback)
        
        self.details.go_back_sidebar()

    def __on_donate_clicked(self, _widget) -> None:
        webbrowser.open_new_tab("https://usebottles.com/funding/")

    def __intel_link_button(self, url: str, tooltip: str) -> Gtk.Button:
        button = Gtk.Button(
            icon_name="external-link-symbolic",
            valign=Gtk.Align.CENTER,
        )
        button.set_tooltip_text(tooltip)
        button.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
        button.add_css_class("flat")
        button.target_url = url
        button.connect("clicked", self.__on_intel_link_clicked)
        return button

    def __on_intel_link_clicked(self, button) -> None:
        webbrowser.open_new_tab(button.target_url)

    def __on_report_clicked(self, _widget) -> None:
        """
        Show full analysis report as Markdown in a dialog.
        """
        if not self.analysis_results:
            return

        data = self.analysis_results
        details = data.get("details", {})
        metadata = data.get("metadata", {})
        
        lines = []
        lines.append(f"# Eagle Analysis Report")
        lines.append(f"**Target:** `{data.get('name', 'Unknown')}`")
        lines.append("")
        
        lines.append("## Binary Information")
        lines.append(f"- **Product:** {data.get('product_name', 'Unknown')}")
        lines.append(f"- **Publisher:** {data.get('publisher', 'Unknown')}")
        lines.append(f"- **Architecture:** {data.get('arch', 'Unknown')}")
        lines.append(f"- **Minimum OS:** {data.get('min_os', 'Unknown')}")
        lines.append(f"- **Requires Admin:** {'Yes' if data.get('admin') else 'No'}")
        lines.append("")
        
        if metadata:
            lines.append("## Build Metadata")
            if metadata.get("compiler"):
                lines.append(f"- **Compiler:** {metadata.get('compiler')}")
            if metadata.get("build_date"):
                lines.append(f"- **Build Date:** {metadata.get('build_date')}")
            flags = []
            if metadata.get("large_address_aware"):
                flags.append("Large Address Aware")
            if metadata.get("dep_enabled"):
                flags.append("DEP")
            if metadata.get("aslr_enabled"):
                flags.append("ASLR")
            if flags:
                lines.append(f"- **PE Flags:** {', '.join(flags)}")
            lines.append("")

        intel = data.get("intel")
        if intel:
            lines.append("## Community Intelligence")
            lines.append(f"- **Application:** {intel['name']}")
            lines.append(f"- **Source:** {intel['source']}")
            lines.append(f"- **Match:** {intel['match']}")
            if intel.get("source") != "winetricks":
                lines.append(f"- **Tier:** {intel['tier']}")
                lines.append(f"- **Reports:** {intel['reports']}")
                lines.append(
                    f"- **Verdict:** {intel['verdict_yes']} positive / "
                    f"{intel['verdict_no']} negative"
                )
            for note in intel.get("notes", []):
                lines.append(f"- **Note:** {note}")
            for attribution in intel.get("attributions", []):
                lines.append(
                    f"- **Data credit:** [{attribution['name']}]"
                    f"({attribution['url']})"
                )
                for license_info in attribution["licenses"]:
                    lines.append(
                        f"- **Data license ({attribution['name']}):** "
                        f"[{license_info['name']}]({license_info['url']})"
                    )
            if intel.get("source") == "protondb":
                lines.append(
                    "- **Tier method:** Calculated by Eagle Intel, "
                    "not an official ProtonDB rating"
                )
            lines.append("")
        
        lines.append("## Detected Technologies")
        for category in ["Graphics", "Audio", "Runtimes", "Frameworks", "Engines", "Input", "Protection", "Social/DRM", "Installer"]:
            items = details.get(category, [])
            if items:
                lines.append(f"### {category}")
                for item in items:
                    name = "Unknown"
                    source = ""
                    if isinstance(item, dict):
                        name = item.get("name", "Unknown")
                        source = item.get("source", "")
                    else:
                        name = str(item)
                    
                    line = f"- **{name}**"
                    if source:
                        line += f"  \n  *Source: {source}*"
                    lines.append(line)
                lines.append("")
        
        reg_items = details.get("Registry", [])
        if reg_items:
            lines.append("## Registry Modifications")
            lines.append("> These keys indicate potential system-level changes, such as drivers or DRM, which might require specific dependencies.")
            for item in reg_items:
                name = item.get("name", "Unknown")
                source = item.get("source", "")
                keys = item.get("context", [])
                
                lines.append(f"- **{name}**")
                if keys:
                    if isinstance(keys, str):
                         lines.append(f"  - *Found:* `{keys}`")
                    else:
                        lines.append(f"  - *Found:*")
                        for k in keys:
                             lines.append(f"    - `{k}`")
                if source:
                    lines.append(f"  - *Source:* {source}")
            lines.append("")
        
        analysed_files = details.get("Analysed Files", [])
        if analysed_files:
            lines.append("## Analysed Files")
            if details.get("Installer", []):
                lines.append("> Files extracted from the installer during deep scan.")
            else:
                lines.append("> Includes the main executable and any relevant neighbor files found in the same directory.")
            
            for fname in analysed_files:
                lines.append(f"- `{fname}`")
            lines.append("")

        warnings = details.get("Warning", [])
        if warnings:
            lines.append("## Compatibility Warnings")
            for warn in warnings:
                if isinstance(warn, dict):
                    severity = warn.get("severity", "info").upper()
                    name = warn.get("name", "Unknown")
                    desc = warn.get("description", "")
                    src = warn.get("source", "")
                    
                    lines.append(f"### [{severity}] {name}")
                    if desc:
                        lines.append(f"{desc}")
                    if src:
                        lines.append(f"*Source: {src}*")
                else:
                    lines.append(f"- {warn}")
            lines.append("")
        
        suggestions = data.get("suggestions", [])
        deps = [s for s in suggestions if s.get("key", "").startswith("dep_")]
        if deps:
            lines.append("## Recommended Dependencies")
            lines.append("> Install these from the Dependencies section of your bottle.")
            lines.append("")
            for dep in deps:
                lines.append(f"- {dep.get('label', 'Unknown')}")
            lines.append("")
        
        overrides = [s for s in suggestions if not s.get("key", "").startswith("dep_")]
        if overrides:
            lines.append("## Suggested Overrides")
            for ovr in overrides:
                selected = ovr.get("apply", bool(ovr.get("value")))
                status = "[x]" if selected else "[ ]"
                lines.append(f"- {status} {ovr.get('label', 'Unknown')}")
            lines.append("")
        
        lines.append("---")
        lines.append("*Report generated by Eagle (BETA)*")
        
        report = "\n".join(lines)
        SourceDialog(
            parent=self.details.window,
            title=_("Eagle Analysis Report"),
            message=report,
            lang="markdown",
        ).present()
