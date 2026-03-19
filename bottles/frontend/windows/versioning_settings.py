# versioning_settings.py
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


from gettext import gettext as _

from gi.repository import Adw, Gtk

from bottles.backend.models.config import BottleConfig


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-versioning-settings.ui")
class VersioningSettingsDialog(Adw.Window):
    __gtype_name__ = "VersioningSettingsDialog"

    # region Widgets
    switch_auto_versioning = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config: BottleConfig, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)
        self.window = window
        self.config = config
        self.manager = window.manager

        parameters = self.config.Parameters

        # Setup states
        self.switch_auto_versioning.set_active(parameters.versioning_automatic)

        # Connect signals
        self.switch_auto_versioning.connect(
            "state-set", self.__toggle_feature_cb, "versioning_automatic"
        )

    def __toggle_feature(self, state: bool, key: str) -> None:
        """Toggle a specific feature."""
        self.config = self.manager.update_config(
            config=self.config, key=key, value=state, scope="Parameters"
        ).data["config"]

    def __toggle_feature_cb(self, _widget: Gtk.Widget, state: bool, key: str) -> None:
        self.__toggle_feature(state=state, key=key)
