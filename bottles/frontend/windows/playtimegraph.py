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

from datetime import datetime, timedelta
from gettext import gettext as _
from typing import Optional, List, Any

from gi.repository import Gtk, Adw

from bottles.frontend.utils.playtime import PlaytimeService
from bottles.frontend.widgets.playtimechart_weekly import PlaytimeChartWeekly
from bottles.frontend.widgets.playtimechart_hourly import PlaytimeChartHourly
from bottles.frontend.widgets.playtimechart_monthly import PlaytimeChartMonthly


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-playtime-graph.ui")
class PlaytimeGraphDialog(Adw.Window):
    __gtype_name__ = "PlaytimeGraphDialog"

    # region Widgets
    label_program_title: Gtk.Label = Gtk.Template.Child()
    label_today_time: Gtk.Label = Gtk.Template.Child()
    label_week_time: Gtk.Label = Gtk.Template.Child()
    label_week_label: Gtk.Label = Gtk.Template.Child()
    label_week_avg: Gtk.Label = Gtk.Template.Child()
    label_date_range: Gtk.Label = Gtk.Template.Child()
    btn_prev: Gtk.Button = Gtk.Template.Child()
    btn_next: Gtk.Button = Gtk.Template.Child()
    btn_view_week: Gtk.ToggleButton = Gtk.Template.Child()
    btn_view_day: Gtk.ToggleButton = Gtk.Template.Child()
    btn_view_year: Gtk.ToggleButton = Gtk.Template.Child()
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

        self.parent = parent
        self.program_name: str = program_name
        self.program_id: Optional[str] = program_id
        self.bottle_id: Optional[str] = bottle_id
        self.current_week_offset: int = 0  # 0 = current week, -1 = previous week, etc.
        self.current_view: str = "week"  # "week", "day", or "year"
        self._chart_weekly: Optional[PlaytimeChartWeekly] = None
        self._chart_hourly: Optional[PlaytimeChartHourly] = None
        self._chart_monthly: Optional[PlaytimeChartMonthly] = None

        self.label_program_title.set_label(program_name)  # type: ignore

        # Connect signals
        self.btn_prev.connect("clicked", self.__on_prev_week)  # type: ignore
        self.btn_next.connect("clicked", self.__on_next_week)  # type: ignore
        self.btn_view_week.connect("toggled", self.__on_view_toggled, "week")  # type: ignore
        self.btn_view_day.connect("toggled", self.__on_view_toggled, "day")  # type: ignore
        self.btn_view_year.connect("toggled", self.__on_view_toggled, "year")  # type: ignore

        self.__load_data()

    def __on_view_toggled(self, button: Gtk.ToggleButton, view: str) -> None:
        """Handle view toggle button clicks."""
        if not button.get_active():
            return

        self.current_view = view
        self.current_week_offset = 0  # Reset navigation when switching views
        self.__load_data()

        # Update navigation button tooltips based on view
        if view == "week":
            self.btn_prev.set_tooltip_text(_("Previous Week"))  # type: ignore
            self.btn_next.set_tooltip_text(_("Next Week"))  # type: ignore
        elif view == "day":
            self.btn_prev.set_tooltip_text(_("Previous Day"))  # type: ignore
            self.btn_next.set_tooltip_text(_("Next Day"))  # type: ignore
        elif view == "year":
            self.btn_prev.set_tooltip_text(_("Previous Year"))  # type: ignore
            self.btn_next.set_tooltip_text(_("Next Year"))  # type: ignore

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
        """Load and display playtime data from the database."""
        today = datetime.now()

        # Update date range label and navigation based on view
        if self.current_view == "week":
            week_start = (
                today
                - timedelta(days=today.weekday())
                + timedelta(weeks=self.current_week_offset)
            )
            week_end = week_start + timedelta(days=6)
            date_range = _("{} – {}").format(
                week_start.strftime("%b %-d"), week_end.strftime("%b %-d")
            )
            self.btn_next.set_sensitive(self.current_week_offset < 0)  # type: ignore

        elif self.current_view == "day":
            target_date = today + timedelta(days=self.current_week_offset)
            date_range = target_date.strftime("%B %-d, %Y")
            self.btn_next.set_sensitive(self.current_week_offset < 0)  # type: ignore

        elif self.current_view == "year":
            target_year = today.year + self.current_week_offset
            date_range = str(target_year)
            self.btn_next.set_sensitive(self.current_week_offset < 0)  # type: ignore

        self.label_date_range.set_label(date_range)  # type: ignore

        # Render bar chart based on current view
        if self.current_view == "week":
            daily_data = self.__get_weekly_data()
            self.__render_chart(daily_data)

            # Convert Python weekday (Mon=0) to SQL day_of_week (Sun=0)
            today_index = (today.weekday() + 1) % 7
            today_minutes = (
                daily_data[today_index] if self.current_week_offset == 0 else 0
            )
            period_minutes = sum(daily_data)
            period_avg_minutes = period_minutes // 7 if period_minutes > 0 else 0
            period_label = (
                _("This Week") if self.current_week_offset == 0 else _("Weekly")
            )
            avg_label = _("Daily Average: {}")

        elif self.current_view == "day":
            hourly_data = self.__get_hourly_data()
            self.__render_chart(hourly_data)

            # Calculate daily stats
            today_minutes = sum(hourly_data) if self.current_week_offset == 0 else 0
            period_minutes = sum(hourly_data)
            # Average divides total time by number of hours with data (not zero)
            hours_with_data = sum(1 for minutes in hourly_data if minutes > 0)
            period_avg_minutes = (
                period_minutes // hours_with_data if hours_with_data > 0 else 0
            )
            period_label = _("Today") if self.current_week_offset == 0 else _("Daily")
            avg_label = _("Hourly Average: {}")

        elif self.current_view == "year":
            monthly_data = self.__get_monthly_data()
            self.__render_chart(monthly_data)

            today_minutes = 0
            period_minutes = sum(monthly_data)
            period_avg_minutes = period_minutes // 12 if period_minutes > 0 else 0
            period_label = (
                _("This Year") if self.current_week_offset == 0 else _("Yearly")
            )
            avg_label = _("Monthly Average: {}")

        self.label_today_time.set_label(self.__format_time(today_minutes))  # type: ignore

        self.label_week_time.set_label(self.__format_time(period_minutes))  # type: ignore
        self.label_week_label.set_label(period_label)  # type: ignore
        self.label_week_avg.set_label(  # type: ignore
            avg_label.format(self.__format_time(period_avg_minutes))
        )

        # Get period-specific stats and global last played from database
        service = PlaytimeService(self.parent.manager)
        if self.bottle_id and self.program_id:
            # Get period-specific session count based on current view
            if self.current_view == "week":
                session_count = service.get_weekly_session_count(
                    bottle_id=self.bottle_id,
                    program_id=self.program_id,
                    week_offset=self.current_week_offset,
                )
            elif self.current_view == "day":
                target_date = datetime.now() + timedelta(days=self.current_week_offset)
                date_str = target_date.strftime("%Y-%m-%d")
                session_count = service.get_daily_session_count(
                    bottle_id=self.bottle_id,
                    program_id=self.program_id,
                    date_str=date_str,
                )
            elif self.current_view == "year":
                target_year = datetime.now().year + self.current_week_offset
                session_count = service.get_yearly_session_count(
                    bottle_id=self.bottle_id,
                    program_id=self.program_id,
                    year=target_year,
                )
            else:
                session_count = 0

            # Get global program record for last played (always global)
            record = service.get_program_playtime(
                bottle_id=self.bottle_id,
                bottle_path=None,
                program_name=self.program_name,
                program_path=None,
                program_id=self.program_id,
            )

            if record:
                # Display period total and session count with smart formatting
                self.label_total_time.set_label(self.__format_time(period_minutes))  # type: ignore
                self.label_sessions_count.set_label(str(session_count))  # type: ignore

                # Format last played (always global)
                last_played_text = service.format_last_played(record.last_played)
                self.label_last_played.set_label(last_played_text)  # type: ignore
            else:
                # No data available
                self.label_total_time.set_label(_("0h 0m"))  # type: ignore
                self.label_sessions_count.set_label("0")  # type: ignore
                self.label_last_played.set_label(_("Never"))  # type: ignore
        else:
            # Missing IDs, show zeros
            self.label_total_time.set_label(_("0h 0m"))  # type: ignore
            self.label_sessions_count.set_label("0")  # type: ignore
            self.label_last_played.set_label(_("Never"))  # type: ignore

    def __get_weekly_data(self) -> List[int]:
        """Retrieve weekly playtime data from the database."""
        # Check if we have required IDs
        if not self.bottle_id or not self.program_id:
            return [0] * 7

        service = PlaytimeService(self.parent.manager)
        daily_data = service.get_weekly_data(
            bottle_id=self.bottle_id,
            program_id=self.program_id,
            week_offset=self.current_week_offset,
        )

        return daily_data

    def __get_hourly_data(self) -> List[int]:
        """Retrieve hourly playtime data for a specific day."""
        if not self.bottle_id or not self.program_id:
            return [0] * 24

        # Calculate date based on offset
        target_date = datetime.now() + timedelta(days=self.current_week_offset)
        date_str = target_date.strftime("%Y-%m-%d")

        service = PlaytimeService(self.parent.manager)
        hourly_data = service.get_hourly_data(
            bottle_id=self.bottle_id, program_id=self.program_id, date_str=date_str
        )

        return hourly_data

    def __get_monthly_data(self) -> List[int]:
        """Retrieve monthly playtime data for a specific year."""
        if not self.bottle_id or not self.program_id:
            return [0] * 12

        # Calculate year based on offset
        target_year = datetime.now().year + self.current_week_offset

        service = PlaytimeService(self.parent.manager)
        monthly_data = service.get_monthly_data(
            bottle_id=self.bottle_id, program_id=self.program_id, year=target_year
        )

        return monthly_data

    def __render_chart(self, data: List[int]) -> None:
        """Render the appropriate chart widget based on current view."""
        # Clear existing content
        while child := self.chart_container.get_first_child():  # type: ignore
            self.chart_container.remove(child)  # type: ignore

        # Create or reuse appropriate chart widget based on view
        if self.current_view == "week":
            if self._chart_weekly is None:
                self._chart_weekly = PlaytimeChartWeekly()
            self._chart_weekly.set_daily_data(data)
            self.chart_container.append(self._chart_weekly)  # type: ignore

        elif self.current_view == "day":
            if self._chart_hourly is None:
                self._chart_hourly = PlaytimeChartHourly()
            self._chart_hourly.set_hourly_data(data)
            self.chart_container.append(self._chart_hourly)  # type: ignore

        elif self.current_view == "year":
            if self._chart_monthly is None:
                self._chart_monthly = PlaytimeChartMonthly()
            self._chart_monthly.set_monthly_data(data)
            self.chart_container.append(self._chart_monthly)  # type: ignore

    def __format_time(self, minutes: int) -> str:
        """Format minutes into human-readable time string."""
        if minutes == 0:
            return _("No Data")
        return PlaytimeService.format_playtime(minutes * 60)
