# vkbasalt.py
#
# Copyright 2022 Hari Rana / TheEvilSkeleton <theevilskeleton@riseup.net>
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

'''
Terminologies:
--------------
cas: Contrast Adaptive Sharpening
dls: Denoised Luma Sharpening
fxaa: Fast Approximate Anti-Aliasing
smaa: Subpixel Morphological Anti-Aliasing
clut (or lut): Color LookUp Table
'''

import os
from gi.repository import Gtk, GLib, Adw, Gdk
from bottles.backend.utils.vkbasalt import parse, ParseConfig
from bottles.backend.utils.manager import ManagerUtils
from bottles.frontend.windows.filechooser import FileChooser  # pyright: reportMissingImports=false
from bottles.backend.logger import Logger  # pyright: reportMissingImports=false

logging = Logger()

class VkBasaltSettings:
    default = False
    effects = False
    output = False
    disable_on_launch = False
    toggle_key = False
    cas_sharpness = False
    dls_sharpness = False
    dls_denoise = False
    fxaa_subpixel_quality = False
    fxaa_quality_edge_threshold = False
    fxaa_quality_edge_threshold_min = False
    smaa_edge_detection = False
    smaa_threshold = False
    smaa_max_search_steps = False
    smaa_max_search_steps_diagonal = False
    smaa_corner_rounding = False
    lut_file_path = False
    exec = False

@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-vkbasalt.ui')
class VkBasaltDialog(Adw.Window):
    __gtype_name__ = 'VkBasaltDialog'

    # Region Widgets
    switch_default = Gtk.Template.Child()
    group_effects = Gtk.Template.Child()
    expander_cas = Gtk.Template.Child()
    expander_dls = Gtk.Template.Child()
    expander_fxaa = Gtk.Template.Child()
    expander_smaa = Gtk.Template.Child()
    spin_cas_sharpness = Gtk.Template.Child()
    spin_dls_sharpness = Gtk.Template.Child()
    spin_dls_denoise = Gtk.Template.Child()
    spin_fxaa_subpixel_quality = Gtk.Template.Child()
    spin_fxaa_quality_edge_threshold = Gtk.Template.Child()
    spin_fxaa_quality_edge_threshold_min = Gtk.Template.Child()
    toggle_luma = Gtk.Template.Child()
    toggle_color = Gtk.Template.Child()
    spin_smaa_threshold = Gtk.Template.Child()
    spin_smaa_max_search_steps = Gtk.Template.Child()
    spin_smaa_max_search_steps_diagonal = Gtk.Template.Child()
    spin_smaa_corner_rounding = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()

    def __init__(self, parent_window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent_window)

        # Common variables and references
        self.window = parent_window
        self.manager = parent_window.manager
        self.config = config
        conf = os.path.join(ManagerUtils.get_bottle_path(self.config), "vkBasalt.conf") # Configuration file location

        self.effects = {
            "cas": self.expander_cas,
            "dls": self.expander_dls,
            "fxaa": self.expander_fxaa,
            "smaa": self.expander_smaa,
        }

        # Connect signals
        for widget in self.effects.values():
            widget.connect("notify::enable-expansion", self.__check_state)
        self.btn_save.connect("clicked", self.__save)
        self.switch_default.connect("state-set", self.__default)
        self.toggle_luma.connect("toggled", self.__change_edge_detection_type, "luma")
        self.toggle_color.connect("toggled", self.__change_edge_detection_type, "color")

        # Check if configuration file exists; parse the configuration file if it exists
        if os.path.isfile(conf):
            VkBasaltSettings = ParseConfig(conf)

            subeffects = self.get_subeffects(VkBasaltSettings)

            # Check if effects are used
            if VkBasaltSettings.effects:
                for effect, widget in self.effects.items():
                    if effect not in VkBasaltSettings.effects:
                        widget.set_enable_expansion(False)
            else:
                VkBasaltSettings.effects = False
                self.effects_widgets(False)

            # Check if subeffects are used
            for conf in subeffects:
                if conf[0] != None:
                    conf[1].set_value(float(conf[0]))

            if VkBasaltSettings.smaa_edge_detection != None:
                if VkBasaltSettings.smaa_edge_detection == "color":
                    self.toggle_color.set_active(True)
                    self.smaa_edge_detection = "color"
                else:
                    self.smaa_edge_detection = "luma"
            else:
                self.smaa_edge_detection = "luma"

        # If configuration file doesn't exist, set everything to default
        else:
            self.switch_default.set_state(True)
            self.smaa_edge_detection = "luma"
            self.effects_widgets(False)

    # Save file
    def __idle_save(self, *args):

        conf = ManagerUtils.get_bottle_path(self.config)

        # Apply default settings and close the dialog if default setting is enabled
        if self.switch_default.get_state() is True:
            VkBasaltSettings.default = True
            VkBasaltSettings.output = False
            conf = os.path.join(conf, "vkBasalt.conf")
            if os.path.isfile(conf):
                logging.info(f"Removing file: {conf}")
                os.remove(conf)
            parse(VkBasaltSettings)
            self.close()
            return GLib.SOURCE_REMOVE
        else:
            VkBasaltSettings.default = False

        # Checks filter settings
        if self.check_effects_states():
            effects = []
            if self.expander_cas.get_enable_expansion() is True:
                effects.append("cas")
                VkBasaltSettings.cas_sharpness = Gtk.Adjustment.get_value(self.spin_cas_sharpness)
            if self.expander_dls.get_enable_expansion() is True:
                effects.append("dls")
                VkBasaltSettings.dls_sharpness = Gtk.Adjustment.get_value(self.spin_dls_sharpness)
                VkBasaltSettings.dls_denoise = Gtk.Adjustment.get_value(self.spin_dls_denoise)
            if self.expander_fxaa.get_enable_expansion() is True:
                effects.append("fxaa")
                VkBasaltSettings.fxaa_subpixel_quality = Gtk.Adjustment.get_value(self.spin_fxaa_subpixel_quality)
                VkBasaltSettings.fxaa_quality_edge_threshold = Gtk.Adjustment.get_value(self.spin_fxaa_quality_edge_threshold)
                VkBasaltSettings.fxaa_quality_edge_threshold_min = Gtk.Adjustment.get_value(self.spin_fxaa_quality_edge_threshold_min)
            if self.expander_smaa.get_enable_expansion() is True:
                effects.append("smaa")
                VkBasaltSettings.smaa_threshold = Gtk.Adjustment.get_value(self.spin_smaa_threshold)
                VkBasaltSettings.smaa_edge_detection = self.smaa_edge_detection
                VkBasaltSettings.smaa_corner_rounding = Gtk.Adjustment.get_value(self.spin_smaa_corner_rounding)
                VkBasaltSettings.smaa_max_search_steps = Gtk.Adjustment.get_value(self.spin_smaa_max_search_steps)
                VkBasaltSettings.smaa_max_search_steps_diagonal = Gtk.Adjustment.get_value(self.spin_smaa_max_search_steps_diagonal)

            VkBasaltSettings.effects = tuple(effects)

        else:
            VkBasaltSettings.effects = False

        VkBasaltSettings.output = conf

        parse(VkBasaltSettings)
        self.close()
        return GLib.SOURCE_REMOVE

    def __save(self, *args):
        GLib.idle_add(self.__idle_save)

    # Enable and disable save button when necessary
    def __check_state(self, *args):
        self.btn_save.set_sensitive(self.check_effects_states())

    # Enable and disable other buttons depending on default button when necessary
    def __default(self, widget, state):
        self.group_effects.set_sensitive(not state)
        self.__check_state()

    # Change edge detection type
    def __change_edge_detection_type(self, widget, edge_detection_type):
        self.smaa_edge_detection = edge_detection_type
        self.toggle_luma.handler_block_by_func(self.__change_edge_detection_type)
        self.toggle_color.handler_block_by_func(self.__change_edge_detection_type)
        if edge_detection_type == "luma":
            self.toggle_color.set_active(False)
            self.toggle_luma.set_active(True)
        elif edge_detection_type == "color":
            self.toggle_color.set_active(True)
            self.toggle_luma.set_active(False)

        self.toggle_luma.handler_unblock_by_func(self.__change_edge_detection_type)
        self.toggle_color.handler_unblock_by_func(self.__change_edge_detection_type)

    def effects_widgets(self, status=True):
        for widget in self.effects.values():
            widget.set_enable_expansion(status)

    def check_effects_states(self):
        if True in [widget.get_enable_expansion() for widget in self.effects.values()]:
            return True
        else:
            return False

    def get_subeffects(self, VkBasaltSettings):
        subeffects = [
            [VkBasaltSettings.cas_sharpness, self.spin_cas_sharpness],
            [VkBasaltSettings.dls_sharpness, self.spin_dls_sharpness],
            [VkBasaltSettings.dls_denoise, self.spin_dls_denoise],
            [VkBasaltSettings.fxaa_subpixel_quality, self.spin_fxaa_subpixel_quality],
            [VkBasaltSettings.fxaa_quality_edge_threshold, self.spin_fxaa_quality_edge_threshold],
            [VkBasaltSettings.fxaa_quality_edge_threshold_min, self.spin_fxaa_quality_edge_threshold_min],
            [VkBasaltSettings.smaa_threshold, self.spin_smaa_threshold],
            [VkBasaltSettings.smaa_max_search_steps, self.spin_smaa_max_search_steps],
            [VkBasaltSettings.smaa_max_search_steps_diagonal, self.spin_smaa_max_search_steps_diagonal],
            [VkBasaltSettings.smaa_corner_rounding, self.spin_smaa_corner_rounding],
        ]
        return subeffects
