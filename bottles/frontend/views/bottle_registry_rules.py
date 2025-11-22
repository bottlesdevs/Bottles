# bottle_registry_rules.py
#
# Copyright 2025
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

from gettext import gettext as _
from typing import Optional

from gi.repository import Adw, GObject, Gtk

from bottles.backend.managers.registry_rule import RegistryRuleManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.registry_rule import RegistryRule
from bottles.frontend.windows.registry_rules import RegistryRuleEntry


@Gtk.Template(resource_path="/com/usebottles/bottles/details-registry-rules.ui")
class RegistryRulesView(Adw.Bin):
    __gtype_name__ = "DetailsRegistryRules"

    __registry: list[RegistryRuleEntry] = []

    # region Widgets
    list_rules = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    btn_add_rule = Gtk.Template.Child()
    stack = Gtk.Template.Child()
    # endregion

    def __init__(self, details, config: BottleConfig, **kwargs):
        super().__init__(**kwargs)

        self.window = details.window
        self.config = config
        self.manager = details.manager

        self.ev_controller = Gtk.EventControllerKey.new()
        self.ev_controller.connect("key-released", self.__search_rules)
        self.entry_search.add_controller(self.ev_controller)
        self.search_bar.set_key_capture_widget(self.window)

        self.btn_add_rule.connect("clicked", self.__open_rule_dialog)

        self.stack.set_visible_child_name("page_empty")

    def update(self, _widget=False, config: Optional[BottleConfig] = None):
        if config is None:
            config = BottleConfig()
        self.config = config

        self.__load_rules()

    def __search_rules(self, *_args):
        terms = self.entry_search.get_text()
        self.list_rules.set_filter_func(self.__filter_rules, terms)

    @staticmethod
    def __filter_rules(row, terms=None):
        text = row.get_title().lower() + row.get_subtitle().lower()
        if terms.lower() in text:
            return True
        return False

    def __load_rules(self):
        self.__clear_rules()

        for rule in RegistryRuleManager.list_rules(self.config):
            entry = RegistryRuleEntry(
                self, rule=rule, config=self.config, manager=self.manager
            )
            self.__registry.append(entry)
            self.list_rules.append(entry)

        self.stack.set_visible_child_name(
            "page_rules" if self.__registry else "page_empty"
        )

    def __clear_rules(self):
        for rule in list(self.__registry):
            if rule.get_parent():
                rule.get_parent().remove(rule)
        self.__registry = []

    def __open_rule_dialog(self, *_args, rule: Optional[RegistryRule] = None):
        dialog = RegistryRulesDialog(
            self.window, manager=self.manager, config=self.config, rule=rule
        )
        dialog.connect("saved", self.__on_rule_saved)
        dialog.present()

    def __on_rule_saved(self, *_args):
        self.__load_rules()

    def populate_form(self, rule: RegistryRule):
        self.__open_rule_dialog(rule=rule)

    def remove_entry(self, entry: RegistryRuleEntry):
        if entry in self.__registry:
            self.__registry.remove(entry)
        if entry.get_parent():
            entry.get_parent().remove(entry)
        self.stack.set_visible_child_name(
            "page_rules" if self.__registry else "page_empty"
        )


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-registry-rules.ui")
class RegistryRulesDialog(Adw.Dialog):
    __gtype_name__ = "RegistryRulesDialog"

    __gsignals__ = {
        "saved": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # region Widgets
    entry_rule_name = Gtk.Template.Child()
    entry_rule_description = Gtk.Template.Child()
    row_triggers = Gtk.Template.Child()
    text_keys = Gtk.Template.Child()
    chk_trigger_components = Gtk.Template.Child()
    chk_trigger_dependencies = Gtk.Template.Child()
    chk_trigger_start_program = Gtk.Template.Child()
    chk_trigger_stop_program = Gtk.Template.Child()
    chk_trigger_all = Gtk.Template.Child()
    switch_run_once = Gtk.Template.Child()
    btn_save_rule = Gtk.Template.Child()
    # endregion

    def __init__(
        self,
        window,
        manager,
        config=None,
        rule: Optional[RegistryRule] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.window = window
        self.config = config
        self.manager = manager

        if rule:
            self.__populate_form(rule)

        self.btn_save_rule.connect("clicked", self.__save_rule)

    def present(self):
        return super().present(self.window)

    def __populate_form(self, rule: RegistryRule):
        self.entry_rule_name.set_text(rule.name)
        self.entry_rule_description.set_text(rule.description)
        self.chk_trigger_components.set_active("components" in rule.triggers)
        self.chk_trigger_dependencies.set_active("dependencies" in rule.triggers)
        self.chk_trigger_start_program.set_active("start_program" in rule.triggers)
        self.chk_trigger_stop_program.set_active("stop_program" in rule.triggers)
        self.chk_trigger_all.set_active("all" in rule.triggers)
        self.text_keys.get_buffer().set_text(rule.keys)
        self.switch_run_once.set_active(rule.run_once)

    def __save_rule(self, *_args):
        name = self.entry_rule_name.get_text().strip()
        buffer = self.text_keys.get_buffer()
        start, end = buffer.get_bounds()
        keys = buffer.get_text(start, end, False).strip()

        if not name or not keys:
            self.window.show_toast(
                _("Name and registry keys are required to save a rule."), timeout=4
            )
            return

        triggers = [
            name
            for name, active in [
                ("components", self.chk_trigger_components.get_active()),
                ("dependencies", self.chk_trigger_dependencies.get_active()),
                ("start_program", self.chk_trigger_start_program.get_active()),
                ("stop_program", self.chk_trigger_stop_program.get_active()),
                ("all", self.chk_trigger_all.get_active()),
            ]
            if active
        ]

        rule = RegistryRule(
            name=name,
            description=self.entry_rule_description.get_text().strip(),
            keys=keys,
            triggers=triggers,
            run_once=self.switch_run_once.get_active(),
        )
        RegistryRuleManager.upsert_rule(self.manager, self.config, rule)
        self.window.show_toast(_("{} saved").format(rule.name))
        self.emit("saved")
        self.close()
