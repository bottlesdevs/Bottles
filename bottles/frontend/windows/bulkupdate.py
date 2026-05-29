# bulkupdate.py
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

from gi.repository import Adw, GLib, Gtk

from bottles.backend.utils.threading import RunAsync


@Gtk.Template(resource_path="/com/usebottles/bottles/bulk-update-dialog.ui")
class BottlesBulkUpdateDialog(Adw.Dialog):
    __gtype_name__ = "BottlesBulkUpdateDialog"

    # region Widgets
    stack = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_apply = Gtk.Template.Child()
    group_components = Gtk.Template.Child()
    group_bottles = Gtk.Template.Child()
    status_progress = Gtk.Template.Child()
    progress_bar = Gtk.Template.Child()
    label_progress = Gtk.Template.Child()

    # endregion

    # Preferred display order for the component checklist.
    __component_order = ["runner", "dxvk", "vkd3d", "nvapi", "latencyflex", "winebridge"]

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        self.window = window
        self.manager = window.manager

        # path -> {"config": BottleConfig, "updates": [update dict, ...]}
        self.__bottle_updates = {}
        # component id -> Adw.SwitchRow
        self.__component_rows = {}
        # path -> Adw.SwitchRow
        self.__bottle_rows = {}
        self.__total = 0

        # collect the bottles that have at least one available update, reusing
        # the same detection used by the per-bottle details page
        component_titles = {}
        for config in self.manager.local_bottles.values():
            updates = self.manager.get_component_updates(config)
            if not updates:
                continue
            self.__bottle_updates[config.Path] = {
                "config": config,
                "updates": updates,
            }
            for update in updates:
                component_titles.setdefault(update["id"], update["title"])

        # populate the component checklist, keeping a stable order
        for component in self.__component_order:
            if component not in component_titles:
                continue
            row = Adw.SwitchRow(title=component_titles[component], active=True)
            row.connect("notify::active", self.__on_selection_changed)
            self.group_components.add(row)
            self.__component_rows[component] = row

        # populate the bottle checklist
        for path, data in self.__bottle_updates.items():
            config = data["config"]
            available = ", ".join(update["title"] for update in data["updates"])
            row = Adw.SwitchRow(title=config.Name, subtitle=available, active=True)
            row.connect("notify::active", self.__on_selection_changed)
            self.group_bottles.add(row)
            self.__bottle_rows[path] = row

        # connect signals
        self.btn_cancel.connect("clicked", self.__on_cancel)
        self.btn_apply.connect("clicked", self.__on_apply)

        self.__on_selection_changed()

    def __selected_components(self) -> list:
        return [c for c, row in self.__component_rows.items() if row.get_active()]

    def __on_selection_changed(self, *_args) -> None:
        has_component = any(
            row.get_active() for row in self.__component_rows.values()
        )
        has_bottle = any(row.get_active() for row in self.__bottle_rows.values())
        self.btn_apply.set_sensitive(has_component and has_bottle)

    def __build_jobs(self) -> list:
        """Return [(path, config, [update dict, ...])] for the current selection."""
        selected = self.__selected_components()
        jobs = []
        for path, row in self.__bottle_rows.items():
            if not row.get_active():
                continue
            data = self.__bottle_updates[path]
            updates = [u for u in data["updates"] if u["id"] in selected]
            if updates:
                jobs.append((path, data["config"], updates))
        return jobs

    def __on_cancel(self, *_args) -> None:
        self.close()

    def __on_apply(self, *_args) -> None:
        jobs = self.__build_jobs()
        if not jobs:
            self.close()
            return

        self.__total = sum(len(updates) for _p, _c, updates in jobs)
        self.progress_bar.set_fraction(0)
        self.label_progress.set_label("")
        self.set_can_close(False)
        self.stack.set_visible_child_name("page_progress")

        RunAsync(self.__run_updates, callback=self.__on_finished, jobs=jobs)

    def __run_updates(self, jobs) -> dict:
        """Worker thread: apply the updates and report progress on the main loop."""
        ok = 0
        failed = 0
        step = 0

        for _path, config, updates in jobs:
            # apply the runner first, so the DLL overrides get re-initialized
            # on top of the new runner prefix
            ordered = sorted(updates, key=lambda u: 0 if u["id"] == "runner" else 1)
            for update in ordered:
                step += 1
                GLib.idle_add(
                    self.__set_progress, step, config.Name, update["title"]
                )

                result = self.manager.apply_component_update(config, update)
                if result and getattr(result, "ok", False):
                    ok += 1
                    data = getattr(result, "data", None)
                    if isinstance(data, dict) and data.get("config"):
                        # carry the updated config forward so the next update
                        # on this bottle does not overwrite the previous one
                        config = data["config"]
                else:
                    failed += 1

        return {"ok": ok, "failed": failed}

    def __set_progress(self, step: int, bottle_name: str, component_title: str) -> bool:
        if self.__total:
            self.progress_bar.set_fraction(step / self.__total)
        self.label_progress.set_label(f"{bottle_name}: {component_title}")
        return False

    def __on_finished(self, result, error=False) -> None:
        ok = result.get("ok", 0) if isinstance(result, dict) else 0
        failed = result.get("failed", 0) if isinstance(result, dict) else 0

        # reload bottles from disk and refresh the list (and the home banner)
        self.manager.check_bottles()
        self.window.page_list.update_bottles_list()

        if failed:
            message = _("Updated {0} components, {1} failed.").format(ok, failed)
        else:
            message = _("Updated {0} components.").format(ok)
        self.window.show_toast(message)

        self.set_can_close(True)
        self.close()
