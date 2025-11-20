# playtimegraph.py
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
#

import random
from datetime import datetime, timedelta
from gettext import gettext as _
from typing import Optional, List, Any

from gi.repository import Gtk, Adw

from bottles.frontend.utils.playtime import PlaytimeService
from bottles.frontend.widgets.playtimechart import PlaytimeChart


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-playtime-graph.ui")
class PlaytimeGraphDialog(Adw.Window):
    __gtype_name__ = "PlaytimeGraphDialog"

    # region Widgets
    label_today_time: Gtk.Label = Gtk.Template.Child()
    label_today_avg: Gtk.Label = Gtk.Template.Child()
    label_week_time: Gtk.Label = Gtk.Template.Child()
    label_week_label: Gtk.Label = Gtk.Template.Child()
    label_week_avg: Gtk.Label = Gtk.Template.Child()
    label_date_range: Gtk.Label = Gtk.Template.Child()
    btn_prev: Gtk.Button = Gtk.Template.Child()
    btn_next: Gtk.Button = Gtk.Template.Child()
    chart_container: Gtk.Box = Gtk.Template.Child()
    label_total_time: Gtk.Label = Gtk.Template.Child()
    label_sessions_count: Gtk.Label = Gtk.Template.Child()
    label_last_played: Gtk.Label = Gtk.Template.Child()
    # endregion

    def __init__(
        self,
        parent: Any,
        program_name: str,
        program_id: Optional[str] = None,
        bottle_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.set_transient_for(parent.window)

        # common variables and references
        self.parent = parent
        self.program_name: str = program_name
        self.program_id: Optional[str] = program_id
        self.bottle_id: Optional[str] = bottle_id
        self.current_week_offset: int = 0  # 0 = current week, -1 = previous week, etc.
        self._chart: Optional[PlaytimeChart] = None

        # Set window title to program name
        self.set_title(program_name)

        # Connect signals
        self.btn_prev.connect("clicked", self.__on_prev_week)  # type: ignore
        self.btn_next.connect("clicked", self.__on_next_week)  # type: ignore

        # Load initial data
        self.__load_data()

    def __on_prev_week(self, _widget: Gtk.Button) -> None:
        """Navigate to previous week."""
        self.current_week_offset -= 1
        self.__load_data()

    def __on_next_week(self, _widget: Gtk.Button) -> None:
        """Navigate to next week."""
        # Don't allow going into the future
        if self.current_week_offset < 0:
            self.current_week_offset += 1
            self.__load_data()

    def __load_data(self) -> None:
        """Load and display playtime data (currently using fake data)."""
        # TODO: Replace with real database queries
        # For now, generate fake data for UI testing

        # Calculate week range
        today = datetime.now()
        week_start = (
            today
            - timedelta(days=today.weekday())
            + timedelta(weeks=self.current_week_offset)
        )
        week_end = week_start + timedelta(days=6)

        # Update date range label
        if self.current_week_offset == 0:
            date_range = _("{} – {}").format(
                week_start.strftime("%b %-d"), week_end.strftime("%b %-d")
            )
        else:
            date_range = _("{} – {}").format(
                week_start.strftime("%b %-d"), week_end.strftime("%b %-d")
            )
        self.label_date_range.set_label(date_range)  # type: ignore

        # Disable next button if on current week
        self.btn_next.set_sensitive(self.current_week_offset < 0)  # type: ignore

        # Generate fake daily data (in minutes)
        daily_data = self.__generate_fake_daily_data()

        # Calculate stats
        today_minutes = (
            daily_data[today.weekday()] if self.current_week_offset == 0 else 0
        )
        week_minutes = sum(daily_data)
        week_avg_minutes = week_minutes // 7 if week_minutes > 0 else 0

        # Format and display current period stats
        self.label_today_time.set_label(self.__format_time(today_minutes))  # type: ignore
        self.label_today_avg.set_label(  # type: ignore
            _("Daily Average: {}").format(self.__format_time(week_avg_minutes))
        )

        self.label_week_time.set_label(self.__format_time(week_minutes))  # type: ignore
        week_label = _("This Week") if self.current_week_offset == 0 else _("Weekly")
        self.label_week_label.set_label(week_label)  # type: ignore
        self.label_week_avg.set_label(  # type: ignore
            _("Daily Average: {}").format(self.__format_time(week_avg_minutes))
        )

        # Generate fake all-time stats
        total_hours = random.randint(10, 200)
        total_minutes = random.randint(0, 59)
        total_sessions = random.randint(5, 100)
        days_ago = random.randint(0, 30)

        # Display all-time stats
        self.label_total_time.set_label(_("{}h {}m").format(total_hours, total_minutes))  # type: ignore
        self.label_sessions_count.set_label(str(total_sessions))  # type: ignore

        if days_ago == 0:
            self.label_last_played.set_label(_("Today"))  # type: ignore
        elif days_ago == 1:
            self.label_last_played.set_label(_("Yesterday"))  # type: ignore
        else:
            self.label_last_played.set_label(_("{} days ago").format(days_ago))  # type: ignore

        # Render bar chart
        self.__render_chart(daily_data)

    def __generate_fake_daily_data(self) -> List[int]:
        """Generate fake daily playtime data for testing (in minutes)."""
        # Sunday to Saturday
        return [
            random.randint(0, 240),  # Sunday
            random.randint(30, 180),  # Monday
            random.randint(60, 300),  # Tuesday
            random.randint(0, 120),  # Wednesday
            random.randint(90, 240),  # Thursday
            random.randint(120, 300),  # Friday
            random.randint(60, 360),  # Saturday
        ]

    def __render_chart(self, daily_data: List[int]) -> None:
        """Render the bar chart with daily playtime data."""
        # Clear existing content
        while child := self.chart_container.get_first_child():  # type: ignore
            self.chart_container.remove(child)  # type: ignore

        # Create or reuse chart widget
        if self._chart is None:
            self._chart = PlaytimeChart()

        # Update chart with new data
        self._chart.set_daily_data(daily_data)

        # Add to container
        self.chart_container.append(self._chart)  # type: ignore

    def __format_time(self, minutes: int) -> str:
        """Format minutes into human-readable time string."""
        return PlaytimeService.format_playtime(minutes * 60)
