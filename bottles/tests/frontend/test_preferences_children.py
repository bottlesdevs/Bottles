import xml.etree.ElementTree as ET

from gi.repository import Gio

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))


def test_preferences_pages_only_contain_preference_groups():
    root = "/com/usebottles/bottles/"
    for name in Gio.resources_enumerate_children(root, Gio.ResourceLookupFlags.NONE):
        if not name.endswith(".ui"):
            continue
        data = Gio.resources_lookup_data(root + name, Gio.ResourceLookupFlags.NONE)
        for node in ET.fromstring(data.get_data()).iter():
            if (
                node.get("class") != "AdwPreferencesPage"
                and node.get("parent") != "AdwPreferencesPage"
            ):
                continue
            for child in node.findall("child/object"):
                assert child.get("class") == "AdwPreferencesGroup", (
                    name,
                    node.attrib,
                    child.attrib,
                )
