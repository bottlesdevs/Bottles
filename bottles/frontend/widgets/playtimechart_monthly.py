# playtimechart_monthly.py
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

"""
PlaytimeChartMonthly Widget

A reusable chart widget for displaying monthly playtime data (yearly breakdown) as a bar chart.
Features:
- 12 bars representing each month of the year (Jan-Dec)
- Dynamic bar sizing and spacing
- Grid lines with time labels
- Tooltips on hover
- Month labels aligned with bars
- Automatic scaling based on data
"""

import math
from gettext import gettext as _
from typing import List, Optional, Dict, Any

from gi.repository import Gtk, Adw
from bottles.frontend.utils.playtime import PlaytimeService


class PlaytimeChartMonthly(Gtk.Box):
    """
    A custom widget for rendering monthly playtime bar charts (yearly breakdown).

    Usage:
        chart = PlaytimeChartMonthly()
        chart.set_monthly_data([1200, 900, 1500, ...])  # Minutes for each month (Jan-Dec)
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)

        # Chart data
        self._daily_data: List[int] = []
        self._chart_data: Dict[str, Any] = {}
        self._hover_x: float = 0
        self._hover_y: float = 0

        # Chart configuration
        self._chart_height: int = 200
        self._num_bars: int = 12  # Always show all 12 months
        self._label_area_width: int = 48
        self._grid_padding: int = 20
        self._last_width: int = 0

        # Create UI structure
        self._build_ui()

        # Monitor widget allocation changes
        self.connect("notify::default-width", self._on_width_changed)

        # Monitor theme changes to update colors
        style_manager = Adw.StyleManager.get_default()
        style_manager.connect("notify::dark", self._on_style_changed)
        style_manager.connect("notify::accent-color", self._on_style_changed)

    def _get_font_scale(self) -> float:
        """Get the current font scale factor from GTK settings."""
        settings = Gtk.Settings.get_default()
        if settings:
            # Get text scaling factor (typically 1.0, but can be 1.25, 1.5, etc.)
            scale = settings.get_property("gtk-xft-dpi") / 96.0 / 1024.0
            return max(scale, 0.8)  # Minimum scale of 0.8
        return 1.0

    def _on_width_changed(self, *_args: Any) -> None:
        """Re-render chart when widget width changes."""
        current_width = self.get_width()
        if current_width > 1 and current_width != self._last_width and self._daily_data:
            self._render_chart()

    def _on_style_changed(self, *_args: Any) -> None:
        """Re-render chart when theme/style changes."""
        # Trigger redraw of both chart and labels to pick up new colors
        if hasattr(self, "_chart_box"):
            chart_area = self._chart_box.get_first_child()
            if chart_area:
                chart_area.queue_draw()
        if hasattr(self, "_day_labels_area"):
            self._day_labels_area.queue_draw()

    def _build_ui(self) -> None:
        """Build the chart UI structure."""
        # Main chart container
        self._chart_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._chart_box.set_spacing(8)
        self._chart_box.set_vexpand(True)
        self.append(self._chart_box)

        # Month labels drawing area
        self._month_labels_area = Gtk.DrawingArea()
        self._month_labels_area.set_content_height(20)
        self._month_labels_area.set_draw_func(self._draw_month_labels)
        self._month_labels_area.set_hexpand(True)
        self.append(self._month_labels_area)

    def set_monthly_data(
        self, monthly_data: List[int], max_hours: Optional[int] = None
    ) -> None:
        """
        Set the monthly playtime data and render the chart.

        Args:
            monthly_data: List of minutes for each month (Jan=0, Feb=1, ..., Dec=11)
            max_hours: Optional maximum hours for grid. If None, calculated automatically.
        """
        self._daily_data = monthly_data
        self._render_chart(max_hours)

    def _render_chart(self, max_hours_override: Optional[int] = None) -> None:
        """Render the bar chart with the current data."""
        # Clear existing content
        while child := self._chart_box.get_first_child():
            self._chart_box.remove(child)

        if not self._daily_data:
            return

        # Calculate grid max (round up to nearest even number of hours)
        max_minutes = max(self._daily_data) if any(self._daily_data) else 1
        max_hours = max_minutes / 60.0

        if max_hours_override is not None:
            grid_max_hours = max_hours_override
        elif max_hours < 1:
            grid_max_hours = 2  # Minimum grid is 2 hours
        else:
            grid_max_hours = math.ceil(max_hours / 2) * 2

        grid_max_minutes = grid_max_hours * 60

        # Dynamic chart sizing
        container_width = self.get_width()
        if container_width <= 1:
            container_width = 614  # Default: 650 - 36 (margins)

        # Check if width changed - re-render if needed
        if container_width != self._last_width and self._last_width > 0:
            self._last_width = container_width
        elif container_width > 1:
            self._last_width = container_width

        num_bars = self._num_bars  # Always 12 bars for monthly view
        available_chart_width = container_width - self._label_area_width

        # Calculate dynamic bar width for 12 months
        min_padding = 40
        min_spacing = 4

        # Calculate space available for bars and spacing
        usable_width = available_chart_width - (2 * min_padding)

        # Calculate bar width: distribute space among bars with minimal spacing
        total_spacing = (num_bars - 1) * min_spacing
        dynamic_bar_width = max(int((usable_width - total_spacing) / num_bars), 20)

        spacing = min_spacing

        # Calculate bar positions
        start_x = min_padding
        chart_width = available_chart_width

        # Store chart data
        self._chart_data = {
            "daily_data": self._daily_data,
            "grid_max_hours": grid_max_hours,
            "grid_max_minutes": grid_max_minutes,
            "bar_positions": [],
            "label_area_width": self._label_area_width,
            "chart_width": chart_width,
            "grid_end_x": 0,  # Will be calculated in draw
        }

        for i in range(num_bars):
            x = start_x + (i * (dynamic_bar_width + spacing))
            self._chart_data["bar_positions"].append((x, dynamic_bar_width))

        # Create drawing area
        chart_area = Gtk.DrawingArea()
        chart_area.set_content_height(self._chart_height)
        chart_area.set_draw_func(self._draw_chart)
        chart_area.set_hexpand(True)
        chart_area.set_vexpand(False)

        # Add tooltip support
        chart_area.set_has_tooltip(True)
        chart_area.connect("query-tooltip", self._on_chart_tooltip)

        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("motion", self._on_chart_motion)
        chart_area.add_controller(motion_controller)

        self._chart_box.append(chart_area)

    def _draw_month_labels(
        self, _area: Gtk.DrawingArea, ctx: Any, _width: float, height: float
    ) -> None:
        """Draw month labels using Cairo."""
        if not self._chart_data or "bar_positions" not in self._chart_data:
            return

        # Month abbreviations (localized)
        month_abbr = [
            _("J"),  # January
            _("F"),  # February
            _("M"),  # March
            _("A"),  # April
            _("M"),  # May
            _("J"),  # June
            _("J"),  # July
            _("A"),  # August
            _("S"),  # September
            _("O"),  # October
            _("N"),  # November
            _("D"),  # December
        ]
        bar_positions = self._chart_data["bar_positions"]

        # Get foreground color from theme
        style_context = self.get_style_context()
        fg_color = style_context.lookup_color("foreground")
        if fg_color[0]:
            ctx.set_source_rgba(
                fg_color[1].red, fg_color[1].green, fg_color[1].blue, 0.7
            )
        else:
            ctx.set_source_rgba(0.5, 0.5, 0.5, 0.7)

        ctx.select_font_face("", 0, 0)  # Default font
        font_scale = self._get_font_scale()
        ctx.set_font_size(10 * font_scale)

        for i, (x, bar_width) in enumerate(bar_positions):
            if i < len(month_abbr):
                text = month_abbr[i]

                # Get text dimensions for centering
                extents = ctx.text_extents(text)
                text_width = extents.width

                # Center text within bar width
                text_x = x + (bar_width - text_width) / 2
                text_y = height / 2 + extents.height / 2

                ctx.move_to(text_x, text_y)
                ctx.show_text(text)

    def _on_chart_motion(
        self, _controller: Gtk.EventControllerMotion, x: float, y: float
    ) -> None:
        """Handle mouse motion."""
        self._hover_x = x
        self._hover_y = y

    def _on_chart_tooltip(
        self,
        widget: Gtk.Widget,
        x: float,
        y: float,
        _keyboard_mode: bool,
        tooltip: Gtk.Tooltip,
    ) -> bool:
        """Show tooltip with time value when hovering over bars."""
        if not self._chart_data:
            return False

        daily_data = self._chart_data["daily_data"]
        grid_max_minutes = self._chart_data["grid_max_minutes"]
        bar_positions = self._chart_data["bar_positions"]

        height = widget.get_height()

        for i, minutes in enumerate(daily_data):
            if minutes > 0:
                bar_x, bar_width = bar_positions[i]
                # Don't add offset - use bar position directly
                bar_height = (minutes / grid_max_minutes) * height
                bar_height = max(bar_height, 4)
                bar_y = height - bar_height

                if bar_x <= x <= bar_x + bar_width and bar_y <= y <= height:
                    tooltip.set_text(self._format_time(minutes))
                    return True

        return False

    def _draw_chart(
        self, _area: Gtk.DrawingArea, ctx: Any, width: float, height: float
    ) -> None:
        """Draw the complete chart: grid lines and bars."""
        if not self._chart_data:
            return

        daily_data = self._chart_data["daily_data"]
        grid_max_hours = self._chart_data["grid_max_hours"]
        grid_max_minutes = self._chart_data["grid_max_minutes"]

        # Recalculate bar positions based on actual width
        num_bars = self._num_bars  # Always 12 bars

        # Calculate actual label width based on font size
        ctx.select_font_face("", 0, 0)
        font_scale = self._get_font_scale()
        ctx.set_font_size(10 * font_scale)

        # Measure the widest label
        max_label = f"{grid_max_hours}h"
        extents = ctx.text_extents(max_label)
        label_text_width = extents.width + 10  # Add 10px padding

        # Calculate bar layout with dynamic spacing and dynamic bar width
        min_spacing = 4  # Minimum spacing between bars
        min_padding = 10  # Minimum left/right padding

        # Calculate available space for chart (excluding label area on right)
        available_chart_width = width - label_text_width

        # Calculate dynamic bar width
        usable_width = available_chart_width - (2 * min_padding)
        total_spacing = (num_bars - 1) * min_spacing
        dynamic_bar_width = max(int((usable_width - total_spacing) / num_bars), 20)

        # Calculate actual spacing after accounting for bar widths
        total_bars_width = num_bars * dynamic_bar_width
        remaining_space = available_chart_width - total_bars_width

        if num_bars > 1:
            spacing = remaining_space / (
                num_bars + 1
            )  # Space on sides and between bars
            spacing = max(spacing, min_spacing)
        else:
            spacing = (available_chart_width - dynamic_bar_width) / 2

        start_x = spacing + label_text_width / 2  # Left padding + centering offset

        bar_positions: List[tuple[float, int]] = []
        for i in range(num_bars):
            x = start_x + (i * (dynamic_bar_width + spacing))
            bar_positions.append((x, dynamic_bar_width))

        # Update stored bar positions with recalculated values
        self._chart_data["bar_positions"] = bar_positions

        # Trigger month labels redraw (they're now drawn with Cairo)
        if hasattr(self, "_month_labels_area"):
            self._month_labels_area.queue_draw()

        # Calculate grid boundaries
        # Grid extends symmetrically: spacing on both sides (compensate for centering offset)
        if bar_positions:
            last_bar_x: float
            last_bar_width: int
            last_bar_x, last_bar_width = bar_positions[-1]
            rightmost: float = last_bar_x + last_bar_width

            # Symmetric padding: match the left offset
            grid_start_x = 0
            grid_end_x: float = rightmost + spacing - (label_text_width / 2)

            # Store grid_end_x for labels
            self._chart_data["grid_end_x"] = grid_end_x
        else:
            grid_start_x = 0
            grid_end_x = width - label_text_width
            self._chart_data["grid_end_x"] = grid_end_x

        # Draw grid lines
        style_context = self.get_style_context()
        fg_color = style_context.lookup_color("foreground")
        if fg_color[0]:
            ctx.set_source_rgba(
                fg_color[1].red, fg_color[1].green, fg_color[1].blue, 0.25
            )
        else:
            ctx.set_source_rgba(0.5, 0.5, 0.5, 0.25)

        ctx.set_line_width(1)

        pixels_per_hour = height / grid_max_hours

        # Draw only 3 grid lines: 0, middle, and max
        for hour in [0, grid_max_hours // 2, grid_max_hours]:
            y = height - (hour * pixels_per_hour)
            ctx.move_to(grid_start_x, y)
            ctx.line_to(grid_end_x, y)
            ctx.stroke()

        # Draw time labels after grid, positioned at grid end + small gap
        # This creates symmetric padding: left padding = right padding
        label_x: float = grid_end_x + 0  # 0px gap after grid end

        # Set text color for labels
        style_context = self.get_style_context()
        fg_color = style_context.lookup_color("foreground")
        if fg_color[0]:
            ctx.set_source_rgba(
                fg_color[1].red, fg_color[1].green, fg_color[1].blue, 0.7
            )
        else:
            ctx.set_source_rgba(0.5, 0.5, 0.5, 0.7)

        ctx.select_font_face("", 0, 0)
        font_scale = self._get_font_scale()
        ctx.set_font_size(10 * font_scale)

        # Draw only 3 labels: max, middle, and 0
        for hour in [grid_max_hours, grid_max_hours // 2, 0]:
            y = height - (hour * pixels_per_hour)
            text = f"{hour}h"

            # Clamp y to prevent cropping
            y = max(10, min(y, height - 5))

            ctx.move_to(label_x, y + 4)
            ctx.show_text(text)

        # Draw bars
        style_context = self.get_style_context()
        accent_color = style_context.lookup_color("accent_bg_color")
        if accent_color[0]:
            ctx.set_source_rgba(
                accent_color[1].red, accent_color[1].green, accent_color[1].blue, 1.0
            )
        else:
            ctx.set_source_rgba(0.6, 0.4, 0.8, 1.0)

        for i, minutes in enumerate(daily_data):
            if minutes > 0:
                bar_x: float
                bar_w: int
                bar_x, bar_w = bar_positions[i]
                # Don't add offset - bars positioned directly at calculated x

                bar_height = (minutes / grid_max_minutes) * height
                bar_height = max(bar_height, 4)
                y = height - bar_height

                # Draw rounded rectangle
                radius = 5
                ctx.new_sub_path()
                ctx.arc(bar_x + radius, y + radius, radius, 3.14159, 3.14159 * 1.5)
                ctx.arc(bar_x + bar_w - radius, y + radius, radius, 3.14159 * 1.5, 0)
                ctx.line_to(bar_x + bar_w, y + bar_height)
                ctx.line_to(bar_x, y + bar_height)
                ctx.close_path()
                ctx.fill()

        # Draw average line (after bars so it appears on top)
        avg_minutes = sum(daily_data) / len(daily_data) if daily_data else 0
        if avg_minutes > 0:
            avg_y = height - (avg_minutes / grid_max_minutes) * height

            # Set dashed line style with theme-aware color
            style_context = self.get_style_context()
            fg_color = style_context.lookup_color("foreground")
            if fg_color[0]:
                ctx.set_source_rgba(
                    fg_color[1].red, fg_color[1].green, fg_color[1].blue, 0.6
                )
            else:
                ctx.set_source_rgba(0.5, 0.5, 0.5, 0.6)

            ctx.set_line_width(2)
            ctx.set_dash([5, 5])  # 5px dash, 5px gap

            ctx.move_to(grid_start_x, avg_y)
            ctx.line_to(grid_end_x, avg_y)
            ctx.stroke()

            # Reset dash pattern for subsequent drawing
            ctx.set_dash([])

    def _format_time(self, minutes: int) -> str:
        """Format minutes into human-readable time string."""
        return PlaytimeService.format_playtime(minutes * 60)
