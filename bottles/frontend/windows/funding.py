# funding.py
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

import webbrowser
from gettext import gettext as _
from urllib.parse import urlencode

from gi.repository import Adw, Gdk, GObject, Graphene, Gtk


PAYPAL_DONATION_URL = "https://www.paypal.com/donate"
REVOLUT_DONATION_URL = "https://revolut.me/mirkobrombin"
FUNDING_URL = "https://usebottles.com/funding/"
NEXT_ANNOUNCEMENT_URL = (
    "https://usebottles.com/blog/2023-10-05-bottles-next-a-new-chapter.md"
)
DONATION_AMOUNTS = (5, 10, 20, 50)
MIN_DONATION_AMOUNT = 3
REVOLUT_LOGO_SIZE = (72, 16)


def build_paypal_donation_url(amount: int) -> str:
    if amount < MIN_DONATION_AMOUNT:
        raise ValueError("Donation amount is below the minimum")

    params = urlencode(
        {
            "business": "brombin94@gmail.com",
            "amount": str(amount),
            "currency_code": "USD",
            "item_name": "Bottles",
            "return": "https://usebottles.com/?payment=complete#download",
            "cancel_return": "https://usebottles.com/#download",
            "rm": "2",
        }
    )
    return f"{PAYPAL_DONATION_URL}?{params}"


class WordmarkPaintable(GObject.Object, Gdk.Paintable):
    def __init__(self, widget: Gtk.Widget, icon_name: str, size: tuple[int, int]):
        super().__init__()
        self._widget = widget
        self._icon_name = icon_name
        self._width, self._height = size

    def do_get_intrinsic_width(self) -> int:
        return self._width

    def do_get_intrinsic_height(self) -> int:
        return self._height

    def do_get_intrinsic_aspect_ratio(self) -> float:
        return self._width / self._height

    def do_snapshot(self, snapshot: Gtk.Snapshot, width: float, height: float):
        theme = Gtk.IconTheme.get_for_display(self._widget.get_display())
        icon = theme.lookup_icon(
            self._icon_name,
            None,
            self._width,
            self._widget.get_scale_factor(),
            self._widget.get_direction(),
            Gtk.IconLookupFlags.FORCE_SYMBOLIC,
        )
        color = self._widget.get_color()

        snapshot.push_clip(Graphene.Rect().init(0, 0, width, height))
        snapshot.translate(Graphene.Point().init(0, (height - width) / 2))
        icon.snapshot_symbolic(snapshot, width, width, [color] * 4)
        snapshot.pop()


class FundingDialog(Adw.Dialog):
    __gsignals__ = {
        "response": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    channels = (
        (
            "GitHub Sponsors",
            "https://github.com/sponsors/bottlesdevs",
        ),
        ("Liberapay", "https://liberapay.com/bottles"),
        ("Patreon", "https://www.patreon.com/MirkoBrombin"),
        ("All funding options", FUNDING_URL),
    )

    def __init__(self, parent, bottle_count=0, **kwargs):
        super().__init__()
        self.set_content_width(680)
        self.set_content_height(660)
        self.set_title(_("Support Bottles"))

        self._response = "close"
        self._amount_buttons = {}
        self.connect("closed", self.__on_closed)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=_("Support Bottles")))
        toolbar.add_top_bar(header)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        page.set_margin_top(22)
        page.set_margin_bottom(22)
        page.set_margin_start(24)
        page.set_margin_end(24)

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        hero.set_margin_start(12)
        hero.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name("heart-symbolic")
        icon.set_pixel_size(72)
        icon.add_css_class("donate")
        hero.append(icon)

        hero_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hero_text.set_valign(Gtk.Align.CENTER)
        hero_text.set_hexpand(True)

        title = Gtk.Label(label=_("Keep Bottles independent"), xalign=0)
        title.add_css_class("title-1")
        hero_text.append(title)

        description = Gtk.Label(
            label=self.__get_support_message(bottle_count),
            xalign=0,
            wrap=True,
        )
        description.add_css_class("dim-label")
        hero_text.append(description)
        hero.append(hero_text)
        page.append(hero)

        donation_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        donation_card.add_css_class("card")
        donation_card.set_margin_start(2)
        donation_card.set_margin_end(2)

        card_title = Gtk.Label(label=_("One-time contribution"), xalign=0)
        card_title.add_css_class("heading")
        card_title.set_margin_top(16)
        card_title.set_margin_start(18)
        card_title.set_margin_end(18)
        donation_card.append(card_title)

        amount_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        amount_box.set_margin_start(18)
        amount_box.set_margin_end(18)

        for amount in DONATION_AMOUNTS:
            button = Gtk.Button(label=f"${amount}")
            button.add_css_class("pill")
            button.set_hexpand(True)
            button.connect("clicked", self.__select_amount, amount)
            amount_box.append(button)
            self._amount_buttons[amount] = button

        self.amount = Gtk.SpinButton.new_with_range(MIN_DONATION_AMOUNT, 1000, 1)
        self.amount.set_value(10)
        self.amount.set_width_chars(4)
        self.amount.set_tooltip_text(_("Custom amount in USD"))
        self.amount.connect("value-changed", self.__amount_changed)
        amount_box.append(self.amount)
        donation_card.append(amount_box)

        self.btn_paypal = Gtk.Button()
        self.btn_paypal.add_css_class("suggested-action")
        self.btn_paypal.add_css_class("pill")
        self.btn_paypal.set_margin_start(18)
        self.btn_paypal.set_margin_end(18)
        self.btn_paypal.connect("clicked", self.__donate_with_paypal)
        donation_card.append(self.btn_paypal)

        payment_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        payment_row.set_homogeneous(True)
        payment_row.set_margin_start(18)
        payment_row.set_margin_end(18)
        payment_row.set_margin_bottom(16)

        btn_card = Gtk.Button()
        btn_card.add_css_class("pill")
        btn_card.connect("clicked", self.__open_support_url, REVOLUT_DONATION_URL)
        card_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card_content.set_halign(Gtk.Align.CENTER)
        card_content.append(Gtk.Image.new_from_icon_name("credit-card-symbolic"))
        card_content.append(Gtk.Label(label=_("Credit/Debit Card")))
        btn_card.set_child(card_content)
        payment_row.append(btn_card)

        btn_revolut = Gtk.Button()
        btn_revolut.add_css_class("pill")
        btn_revolut.set_tooltip_text("Revolut")
        btn_revolut.update_property([Gtk.AccessibleProperty.LABEL], ["Revolut"])
        btn_revolut.connect("clicked", self.__open_support_url, REVOLUT_DONATION_URL)
        revolut_logo = Gtk.Picture.new_for_paintable(
            WordmarkPaintable(btn_revolut, "revolut-symbolic", REVOLUT_LOGO_SIZE)
        )
        revolut_logo.set_can_shrink(False)
        revolut_logo.set_halign(Gtk.Align.CENTER)
        revolut_logo.set_valign(Gtk.Align.CENTER)
        btn_revolut.set_child(revolut_logo)
        payment_row.append(btn_revolut)
        donation_card.append(payment_row)
        page.append(donation_card)
        self.__amount_changed()

        recurring = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        recurring_title = Gtk.Label(label=_("Support regularly"), xalign=0)
        recurring_title.add_css_class("heading")
        recurring.append(recurring_title)

        channel_grid = Gtk.FlowBox()
        channel_grid.set_column_spacing(8)
        channel_grid.set_row_spacing(8)
        channel_grid.set_homogeneous(True)
        channel_grid.set_min_children_per_line(2)
        channel_grid.set_max_children_per_line(2)
        channel_grid.set_selection_mode(Gtk.SelectionMode.NONE)

        for label, url in self.channels:
            channel_grid.insert(self.__channel_button(_(label), url), -1)

        recurring.append(channel_grid)
        page.append(recurring)

        next_card = Gtk.Button()
        next_card.add_css_class("card")
        next_card.add_css_class("flat")
        next_card.connect("clicked", self.__open_next_announcement)

        next_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        next_icon = Gtk.Image.new_from_icon_name(
            "com.usebottles.bottles-symbolic"
        )
        next_icon.set_pixel_size(32)
        next_icon.set_margin_start(14)
        next_content.append(next_icon)

        next_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        next_text.set_margin_top(12)
        next_text.set_margin_bottom(12)
        next_text.set_margin_end(14)
        next_text.set_hexpand(True)

        next_title = Gtk.Label(
            label=_("Your support also funds Bottles Next"),
            xalign=0,
        )
        next_title.add_css_class("heading")
        next_text.append(next_title)

        next_description = Gtk.Label(
            label=_(
                "Bottles Next is being developed by the Bottles team and "
                "community contributors."
            ),
            xalign=0,
            wrap=True,
        )
        next_description.add_css_class("dim-label")
        next_text.append(next_description)
        next_content.append(next_text)

        next_link = Gtk.Image.new_from_icon_name("external-link-symbolic")
        next_link.set_margin_end(14)
        next_content.append(next_link)
        next_card.set_child(next_content)
        page.append(next_card)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer.set_margin_top(2)

        footer_label = Gtk.Label(label=_("Already supporting Bottles?"), xalign=0)
        footer_label.add_css_class("dim-label")
        footer_label.set_hexpand(True)
        footer.append(footer_label)

        btn_supporter = Gtk.Button(label=_("Mark as supporter"))
        btn_supporter.add_css_class("flat")
        btn_supporter.connect("clicked", self.__mark_supporter)
        footer.append(btn_supporter)

        if kwargs.get("show_dont_show", False):
            btn_dismiss = Gtk.Button(label=_("Don't Show Again"))
            btn_dismiss.add_css_class("flat")
            btn_dismiss.connect("clicked", self.__dont_show_again)
            footer.append(btn_dismiss)

        page.append(footer)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(620)
        clamp.set_tightening_threshold(520)
        clamp.set_child(page)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(clamp)
        toolbar.set_content(scrolled)
        self.set_child(toolbar)

    @staticmethod
    def __get_support_message(bottle_count: int) -> str:
        if bottle_count == 1:
            usage = _("Bottles currently manages one bottle for you.")
        elif bottle_count > 1:
            usage = _(
                "Bottles currently manages {count} bottles for you."
            ).format(count=bottle_count)
        else:
            usage = _("Bottles is developed independently.")

        maintenance = _("This version of Bottles is maintained by one maintainer.")
        return f"{usage} {maintenance}"

    def __channel_button(self, label: str, url: str) -> Gtk.Button:
        button = Gtk.Button()
        button.set_hexpand(True)
        button.connect("clicked", self.__open_support_url, url)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        text = Gtk.Label(label=label, xalign=0)
        text.set_hexpand(True)
        content.append(text)
        content.append(Gtk.Image.new_from_icon_name("external-link-symbolic"))
        button.set_child(content)
        return button

    def __select_amount(self, _button, amount: int):
        self.amount.set_value(amount)

    def __amount_changed(self, *_args):
        amount = self.amount.get_value_as_int()
        self.btn_paypal.set_label(_("Donate ${amount} with PayPal").format(amount=amount))
        for value, button in self._amount_buttons.items():
            if value == amount:
                button.add_css_class("suggested-action")
            else:
                button.remove_css_class("suggested-action")

    def __donate_with_paypal(self, _button):
        amount = self.amount.get_value_as_int()
        self.__open_support_url(None, build_paypal_donation_url(amount))

    def __open_next_announcement(self, _button):
        webbrowser.open_new_tab(NEXT_ANNOUNCEMENT_URL)

    def __open_support_url(self, _button, url: str):
        webbrowser.open_new_tab(url)
        self._response = "donate"
        self.close()

    def __mark_supporter(self, _button):
        self._response = "supporter"
        self.close()

    def __dont_show_again(self, _button):
        self._response = "dismiss"
        self.close()

    def __on_closed(self, *_args):
        self.emit("response", self._response)
