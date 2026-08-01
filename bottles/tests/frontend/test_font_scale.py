from bottles.frontend.utils.gtk import FontScaleManager


class FakeSettings:
    def __init__(self, scale):
        self.scale = scale
        self.handlers = []

    def connect(self, signal, callback):
        assert signal == "changed::font-scale"
        self.handlers.append(callback)

    def get_double(self, key):
        assert key == "font-scale"
        return self.scale

    def set_scale(self, scale):
        self.set_double("font-scale", scale)

    def set_double(self, key, scale):
        assert key == "font-scale"
        self.scale = scale
        for callback in self.handlers:
            callback(self, "font-scale")


class FakeDisplay:
    def __init__(self):
        self.handlers = []

    def connect_after(self, signal, callback):
        assert signal == "setting-changed"
        self.handlers.append(callback)

    def setting_changed(self, setting):
        for callback in self.handlers:
            callback(self, setting)


class FakeGtkSettings:
    def __init__(self, dpi):
        self.system_dpi = dpi
        self.override_dpi = None

    def get_property(self, name):
        assert name == "gtk-xft-dpi"
        return self.override_dpi if self.override_dpi is not None else self.system_dpi

    def set_property(self, name, value):
        assert name == "gtk-xft-dpi"
        self.override_dpi = value

    def reset_property(self, name):
        assert name == "gtk-xft-dpi"
        self.override_dpi = None

    def set_system_dpi(self, dpi):
        self.system_dpi = dpi


def test_font_scale_uses_system_dpi_and_updates_live():
    settings = FakeSettings(1.25)
    gtk_settings = FakeGtkSettings(96 * 1024)
    display = FakeDisplay()

    FontScaleManager(settings, gtk_settings, display)

    assert gtk_settings.get_property("gtk-xft-dpi") == 120 * 1024

    settings.set_scale(1.5)

    assert gtk_settings.get_property("gtk-xft-dpi") == 144 * 1024


def test_font_scale_tracks_system_dpi_changes():
    settings = FakeSettings(1.25)
    gtk_settings = FakeGtkSettings(96 * 1024)
    display = FakeDisplay()
    FontScaleManager(settings, gtk_settings, display)

    gtk_settings.set_system_dpi(108 * 1024)
    display.setting_changed("gtk-xft-dpi")

    assert gtk_settings.get_property("gtk-xft-dpi") == 135 * 1024


def test_system_default_removes_override_and_follows_system_dpi():
    settings = FakeSettings(1.25)
    gtk_settings = FakeGtkSettings(96 * 1024)
    display = FakeDisplay()
    FontScaleManager(settings, gtk_settings, display)

    gtk_settings.set_system_dpi(108 * 1024)
    settings.set_scale(1.0)

    assert gtk_settings.override_dpi is None
    assert gtk_settings.get_property("gtk-xft-dpi") == 108 * 1024

    gtk_settings.set_system_dpi(120 * 1024)
    display.setting_changed("gtk-xft-dpi")

    assert gtk_settings.override_dpi is None
    assert gtk_settings.get_property("gtk-xft-dpi") == 120 * 1024


def test_font_scale_uses_default_dpi_when_gtk_has_no_value():
    settings = FakeSettings(1.5)
    gtk_settings = FakeGtkSettings(-1)
    display = FakeDisplay()

    FontScaleManager(settings, gtk_settings, display)

    assert gtk_settings.get_property("gtk-xft-dpi") == 144 * 1024


def test_font_scale_normalizes_values_not_exposed_by_preferences():
    settings = FakeSettings(1.3)
    gtk_settings = FakeGtkSettings(96 * 1024)
    display = FakeDisplay()

    FontScaleManager(settings, gtk_settings, display)

    assert settings.scale == 1.25
    assert gtk_settings.get_property("gtk-xft-dpi") == 120 * 1024
