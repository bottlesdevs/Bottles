# display_dialog.py
#
# Copyright 2025 The Bottles Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gettext import gettext as _

from gi.repository import Gtk, GLib, Adw

from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.reg import Reg
from bottles.backend.wine.regkeys import RegKeys
from bottles.frontend.gtk import GtkUtils


renderers = ["gl", "gdi", "vulkan"]


@Gtk.Template(resource_path="/com/usebottles/bottles/display-dialog.ui")
class DisplayDialog(Adw.Window):
    __gtype_name__ = "DisplayDialog"

    # Region Widgets
    btn_save = Gtk.Template.Child()
    expander_virtual_desktop = Gtk.Template.Child()
    spin_width = Gtk.Template.Child()
    spin_height = Gtk.Template.Child()
    switch_mouse_capture = Gtk.Template.Child()
    switch_take_focus = Gtk.Template.Child()
    switch_mouse_warp = Gtk.Template.Child()
    switch_decorated = Gtk.Template.Child()
    spin_dpi = Gtk.Template.Child()
    combo_renderer = Gtk.Template.Child()

    def __init__(
        self, parent_window, config, details, queue, widget, spinner_display, **kwargs
    ):
        super().__init__(**kwargs)
        self.set_transient_for(parent_window)

        # Common variables and references
        self.window = parent_window
        self.manager = parent_window.manager
        self.config = config
        self.widget = widget
        self.spinner_display = spinner_display

        # Connect signals
        self.btn_save.connect("clicked", self.__save)

        self.__update(config)

    def __update(self, config):
        self.parameters = config.Parameters

        self.expander_virtual_desktop.set_enable_expansion(
            self.parameters.virtual_desktop
        )
        self.switch_mouse_capture.set_active(self.parameters.fullscreen_capture)
        self.switch_take_focus.set_active(self.parameters.take_focus)
        self.switch_mouse_warp.set_active(self.parameters.mouse_warp)
        self.switch_decorated.set_active(self.parameters.decorated)
        self.spin_dpi.set_value(self.parameters.custom_dpi)

        """Set resolution"""
        virtual_desktop_res = self.parameters.virtual_desktop_res
        resolution = virtual_desktop_res.split("x")
        self.spin_width.set_value(float(resolution[0]))
        self.spin_height.set_value(float(resolution[1]))

        """Set renderer"""
        for index, renderer in enumerate(renderers):
            if self.parameters.renderer == renderer:
                self.combo_renderer.set_selected(index)
                break

    # Save file
    def __idle_save(self, *args):
        """Get resolution"""
        width = int(self.spin_width.get_value())
        height = int(self.spin_height.get_value())
        resolution = f"{width}x{height}"

        """Queue system"""
        self.started = 0
        self.completed = 0

        def add_queue():
            if self.started == 0:
                self.window.show_toast(_("Updating display settings, please wait…"))
                self.spinner_display.start()
                self.started = 1
            self.widget.set_sensitive(False)

        def complete_queue():
            self.completed += 1

        if (
            self.expander_virtual_desktop.get_enable_expansion()
            != self.parameters.virtual_desktop
        ):
            """Toggle virtual desktop"""

            @GtkUtils.run_in_main_loop
            def update(result, error=False):
                self.config = self.manager.update_config(
                    config=self.config,
                    key="virtual_desktop",
                    value=self.expander_virtual_desktop.get_enable_expansion(),
                    scope="Parameters",
                ).data["config"]
                complete_queue()

            add_queue()
            rk = RegKeys(self.config)
            RunAsync(
                task_func=rk.toggle_virtual_desktop,
                callback=update,
                state=self.expander_virtual_desktop.get_enable_expansion(),
                resolution=resolution,
            )

        if (
            self.expander_virtual_desktop.get_enable_expansion()
            and resolution != self.parameters.virtual_desktop_res
        ):
            """Set virtual desktop resolution"""

            @GtkUtils.run_in_main_loop
            def update(result, error=False):
                self.config = self.manager.update_config(
                    config=self.config,
                    key="virtual_desktop_res",
                    value=resolution,
                    scope="Parameters",
                ).data["config"]
                complete_queue()

            add_queue()
            rk = RegKeys(self.config)
            if self.expander_virtual_desktop.get_enable_expansion():
                RunAsync(
                    task_func=rk.toggle_virtual_desktop,
                    callback=update,
                    state=True,
                    resolution=resolution,
                )

        if self.switch_mouse_warp.get_active() != self.parameters.mouse_warp:
            """Set mouse warp"""

            @GtkUtils.run_in_main_loop
            def update(result, error=False):
                self.config = self.manager.update_config(
                    config=self.config,
                    key="mouse_warp",
                    value=self.switch_mouse_warp.get_active(),
                    scope="Parameters",
                ).data["config"]
                complete_queue()

            add_queue()
            rk = RegKeys(self.config)

            RunAsync(
                rk.set_mouse_warp,
                callback=update,
                state=self.switch_mouse_warp.get_active(),
            )

        if self.spin_dpi.get_value() != self.parameters.custom_dpi:
            """Set DPI"""

            @GtkUtils.run_in_main_loop
            def update(result, error=False):
                self.config = self.manager.update_config(
                    config=self.config, key="custom_dpi", value=dpi, scope="Parameters"
                ).data["config"]
                complete_queue()

            add_queue()
            rk = RegKeys(self.config)
            dpi = int(self.spin_dpi.get_value())

            RunAsync(rk.set_dpi, callback=update, value=dpi)

        if renderers[self.combo_renderer.get_selected()] != self.parameters.renderer:
            """Set renderer"""

            @GtkUtils.run_in_main_loop
            def update(result, error=False):
                self.config = self.manager.update_config(
                    config=self.config,
                    key="renderer",
                    value=renderer,
                    scope="Parameters",
                ).data["config"]
                complete_queue()

            add_queue()
            rk = RegKeys(self.config)
            renderer = renderers[self.combo_renderer.get_selected()]

            RunAsync(rk.set_renderer, callback=update, value=renderer)

        def toggle_x11_reg_key(state, rkey, ckey):
            """Update x11 registry keys"""

            @GtkUtils.run_in_main_loop
            def update(result, error=False):
                self.config = self.manager.update_config(
                    config=self.config, key=ckey, value=state, scope="Parameters"
                ).data["config"]
                complete_queue()

            add_queue()
            reg = Reg(self.config)
            _rule = "Y" if state else "N"

            RunAsync(
                reg.add,
                callback=update,
                key="HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver",
                value=rkey,
                data=_rule,
            )

        if self.switch_mouse_capture.get_active() != self.parameters.fullscreen_capture:
            toggle_x11_reg_key(
                self.switch_mouse_capture.get_active(),
                "GrabFullscreen",
                "fullscreen_capture",
            )
        if self.switch_take_focus.get_active() != self.parameters.take_focus:
            toggle_x11_reg_key(
                self.switch_take_focus.get_active(), "UseTakeFocus", "take_focus"
            )
        if self.switch_decorated.get_active() != self.parameters.decorated:
            toggle_x11_reg_key(
                self.switch_decorated.get_active(), "Decorated", "decorated"
            )

        """Close window"""
        self.close()
        return GLib.SOURCE_REMOVE

    def __save(self, *args):
        GLib.idle_add(self.__idle_save)
