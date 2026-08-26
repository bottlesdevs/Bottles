import os

import pytest

from bottles.backend.utils import wine as wine_module
from bottles.backend.utils.wine import WineUtils


def test_creates_shared_wine_and_proton_user_profile(tmp_path):
    prefix = tmp_path / "prefix"

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True

    user_dir = prefix / "drive_c" / "users" / "mirko"
    steamuser = prefix / "drive_c" / "users" / "steamuser"
    assert user_dir.is_dir()
    assert steamuser.is_symlink()
    assert os.readlink(steamuser) == "mirko"
    assert steamuser.resolve() == user_dir


def test_profile_alias_uses_real_users_directory_for_linked_home(tmp_path):
    real_home = tmp_path / "var" / "home"
    real_home.mkdir(parents=True)
    linked_home = tmp_path / "home"
    linked_home.symlink_to(real_home, target_is_directory=True)
    prefix = linked_home / "mirko" / ".local" / "share" / "bottles" / "Test"

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True

    steamuser = prefix / "drive_c" / "users" / "steamuser"
    assert os.readlink(steamuser) == "mirko"
    assert steamuser.resolve() == prefix.resolve() / "drive_c" / "users" / "mirko"


def test_preserves_existing_steamuser_profile(tmp_path):
    prefix = tmp_path / "prefix"
    steamuser = prefix / "drive_c" / "users" / "steamuser"
    steamuser.mkdir(parents=True)
    marker = steamuser / "save.dat"
    marker.write_text("save")

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True

    assert steamuser.is_dir()
    assert not steamuser.is_symlink()
    assert marker.read_text() == "save"
    host_user = prefix / "drive_c" / "users" / "mirko"
    assert host_user.is_symlink()
    assert os.readlink(host_user) == "steamuser"
    assert (host_user / "save.dat").read_text() == "save"


def test_links_steamuser_to_existing_host_profile(tmp_path):
    prefix = tmp_path / "prefix"
    host_user = prefix / "drive_c" / "users" / "mirko"
    host_user.mkdir(parents=True)
    (host_user / "save.dat").write_text("save")

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True

    steamuser = prefix / "drive_c" / "users" / "steamuser"
    assert steamuser.is_symlink()
    assert os.readlink(steamuser) == "mirko"
    assert (steamuser / "save.dat").read_text() == "save"


def test_accepts_existing_shared_profile_idempotently(tmp_path):
    prefix = tmp_path / "prefix"
    host_user = prefix / "drive_c" / "users" / "mirko"
    host_user.mkdir(parents=True)
    steamuser = host_user.parent / "steamuser"
    steamuser.symlink_to("mirko")

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True
    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True

    assert steamuser.is_symlink()
    assert os.readlink(steamuser) == "mirko"


def test_preserves_single_template_profile_as_canonical(tmp_path):
    prefix = tmp_path / "prefix"
    template_user = prefix / "drive_c" / "users" / "template-user"
    template_user.mkdir(parents=True)
    (template_user / "save.dat").write_text("save")

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True

    users = prefix / "drive_c" / "users"
    assert os.readlink(users / "mirko") == "template-user"
    assert os.readlink(users / "steamuser") == "template-user"
    assert (users / "mirko" / "save.dat").read_text() == "save"
    assert (users / "steamuser" / "save.dat").read_text() == "save"


def test_preserves_conflicting_real_profiles(tmp_path):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    host_user = users / "mirko"
    steamuser = users / "steamuser"
    host_user.mkdir(parents=True)
    steamuser.mkdir()
    (host_user / "host-save.dat").write_text("host")
    (steamuser / "proton-save.dat").write_text("proton")

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True

    assert not host_user.is_symlink()
    assert not steamuser.is_symlink()
    assert (host_user / "host-save.dat").read_text() == "host"
    assert (steamuser / "proton-save.dat").read_text() == "proton"


def test_rejects_profile_link_outside_users_directory(tmp_path):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    outside = tmp_path / "outside"
    users.mkdir(parents=True)
    outside.mkdir()
    (users / "steamuser").symlink_to(outside)

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is False

    assert not (users / "mirko").exists()
    assert (users / "steamuser").resolve() == outside


@pytest.mark.parametrize("public_name", ["Public", "public"])
def test_rejects_profile_alias_to_public_directory(tmp_path, public_name):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    public = users / public_name
    public.mkdir(parents=True)
    (users / "steamuser").symlink_to(public_name)

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is False

    assert not (users / "mirko").exists()
    assert (users / "steamuser").resolve() == public


@pytest.mark.parametrize("public_name", ["Public", "public"])
def test_rejects_profile_alias_below_public_directory(tmp_path, public_name):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    nested = users / public_name / "nested"
    nested.mkdir(parents=True)
    (users / "steamuser").symlink_to(f"{public_name}/nested")

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is False

    assert not (users / "mirko").exists()
    assert (users / "steamuser").resolve() == nested


def test_rejects_linked_public_directory(tmp_path):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    outside = tmp_path / "outside"
    users.mkdir(parents=True)
    outside.mkdir()
    (users / "Public").symlink_to(outside)

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is False

    assert not (users / "mirko").exists()
    assert (users / "Public").resolve() == outside


@pytest.mark.parametrize("kind", ["broken", "cyclic"])
def test_rejects_unresolvable_profile_links(tmp_path, kind):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    users.mkdir(parents=True)
    if kind == "broken":
        (users / "steamuser").symlink_to("missing")
    else:
        (users / "steamuser").symlink_to("mirko")
        (users / "mirko").symlink_to("steamuser")

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is False


def test_relative_profile_alias_survives_prefix_move(tmp_path):
    prefix = tmp_path / "prefix"
    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True
    (prefix / "drive_c" / "users" / "mirko" / "save.dat").write_text("save")

    relocated = tmp_path / "relocated"
    prefix.rename(relocated)

    steamuser = relocated / "drive_c" / "users" / "steamuser"
    assert os.readlink(steamuser) == "mirko"
    assert (steamuser / "save.dat").read_text() == "save"


def test_steamuser_host_name_does_not_create_self_link(tmp_path):
    prefix = tmp_path / "prefix"

    assert WineUtils.ensure_user_profile_alias(str(prefix), "steamuser") is True

    steamuser = prefix / "drive_c" / "users" / "steamuser"
    assert steamuser.is_dir()
    assert not steamuser.is_symlink()


def test_case_variant_steamuser_gets_lowercase_alias(tmp_path):
    prefix = tmp_path / "prefix"

    assert WineUtils.ensure_user_profile_alias(str(prefix), "SteamUser") is True

    users = prefix / "drive_c" / "users"
    assert (users / "SteamUser").is_dir()
    assert (users / "steamuser").is_symlink()
    assert os.readlink(users / "steamuser") == "SteamUser"


def test_uses_user_environment_before_account_database(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    monkeypatch.setenv("USER", "environment-user")
    monkeypatch.setattr(
        wine_module.pwd,
        "getpwuid",
        lambda _uid: type("Account", (), {"pw_name": "account-user"})(),
    )

    assert WineUtils.ensure_user_profile_alias(str(prefix)) is True

    users = prefix / "drive_c" / "users"
    assert (users / "environment-user").is_dir()
    assert not (users / "account-user").exists()


def test_uses_account_database_when_user_environment_is_missing(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.setattr(
        wine_module.pwd,
        "getpwuid",
        lambda _uid: type("Account", (), {"pw_name": "account-user"})(),
    )

    assert WineUtils.ensure_user_profile_alias(str(prefix)) is True

    users = prefix / "drive_c" / "users"
    assert (users / "account-user").is_dir()
    assert os.readlink(users / "steamuser") == "account-user"


def test_uses_wine_when_user_lookup_fails(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    monkeypatch.delenv("USER", raising=False)

    def raise_key_error(_uid):
        raise KeyError

    monkeypatch.setattr(wine_module.pwd, "getpwuid", raise_key_error)

    assert WineUtils.ensure_user_profile_alias(str(prefix)) is True

    users = prefix / "drive_c" / "users"
    assert (users / "wine").is_dir()
    assert os.readlink(users / "steamuser") == "wine"


@pytest.mark.parametrize(
    ("username", "normalized"),
    [
        ("nested/user", "user"),
        ("../outside", "outside"),
        ("nested\\user", "user"),
        ("..\\outside", "outside"),
        ("nested/path\\user", "user"),
    ],
)
def test_normalizes_user_name_like_wine(tmp_path, username, normalized):
    prefix = tmp_path / "prefix"

    assert WineUtils.ensure_user_profile_alias(str(prefix), username) is True

    users = prefix / "drive_c" / "users"
    assert (users / normalized).is_dir()
    assert os.readlink(users / "steamuser") == normalized


def test_rolls_back_new_profile_when_alias_creation_fails(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"

    def fail_symlink(_target, _link):
        raise OSError

    monkeypatch.setattr(wine_module.os, "symlink", fail_symlink)

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is False

    users = prefix / "drive_c" / "users"
    assert not (users / "mirko").exists()
    assert not (users / "steamuser").exists()


def test_rolls_back_first_alias_when_second_alias_creation_fails(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    template_user = users / "template-user"
    template_user.mkdir(parents=True)
    marker = template_user / "save.dat"
    marker.write_text("save")
    symlink = wine_module.os.symlink
    calls = 0

    def fail_second_symlink(target, link):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError
        symlink(target, link)

    monkeypatch.setattr(wine_module.os, "symlink", fail_second_symlink)

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is False

    assert not (users / "mirko").exists()
    assert not (users / "steamuser").exists()
    assert marker.read_text() == "save"


def test_get_user_dir_prefers_real_profile_over_alias(tmp_path):
    prefix = tmp_path / "prefix"
    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True

    assert WineUtils.get_user_dir(str(prefix)) == "mirko"


def test_get_user_dir_rejects_conflicting_profiles(tmp_path):
    users = tmp_path / "prefix" / "drive_c" / "users"
    (users / "zeta").mkdir(parents=True)
    (users / "alpha").mkdir()
    (users / "Public").mkdir()

    with pytest.raises(Exception, match="Multiple user directories"):
        WineUtils.get_user_dir(str(tmp_path / "prefix"))


@pytest.mark.parametrize(
    "username",
    [
        "",
        ".",
        "..",
        "Public",
        "PUBLIC",
        "nested/Public",
        "nested\\Public",
        "null\0user",
    ],
)
def test_rejects_unsafe_user_profile_names(tmp_path, username):
    prefix = tmp_path / "prefix"

    assert WineUtils.ensure_user_profile_alias(str(prefix), username) is False

    assert not (prefix / "drive_c" / "users").exists()


def test_unlinks_only_new_user_profile_links(tmp_path):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    existing = users / "mirko"
    existing.mkdir(parents=True)
    existing_target = tmp_path / "existing-target"
    existing_target.mkdir()
    (existing / "Custom").symlink_to(existing_target)
    existing_profiles = WineUtils.get_user_profile_ids(str(prefix))

    created = users / "steamuser"
    created.mkdir()
    created_target = tmp_path / "created-target"
    created_target.mkdir()
    (created / "Documents").symlink_to(created_target)

    assert WineUtils.unlink_user_profile_links(str(prefix), existing_profiles) is True

    assert (existing / "Custom").is_symlink()
    assert (created / "Documents").is_dir()
    assert not (created / "Documents").is_symlink()


def test_unlinks_nested_shell_folder_links(tmp_path):
    prefix = tmp_path / "prefix"
    profile = prefix / "drive_c" / "users" / "steamuser"
    documents = profile / "Documents"
    windows = profile / "AppData" / "Roaming" / "Microsoft" / "Windows"
    documents.mkdir(parents=True)
    windows.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    (documents / "My Music").symlink_to(target)
    (windows / "Templates").symlink_to(target)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is True

    assert (documents / "My Music").is_dir()
    assert not (documents / "My Music").is_symlink()
    assert (windows / "Templates").is_dir()
    assert not (windows / "Templates").is_symlink()


def test_does_not_follow_profile_or_shell_folder_links(tmp_path):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    users.mkdir(parents=True)
    outside_profile = tmp_path / "outside-profile"
    outside_profile.mkdir()
    outside_target = tmp_path / "outside-target"
    outside_target.mkdir()
    outside_link = outside_profile / "Documents"
    outside_link.symlink_to(outside_target)
    (users / "escaped").symlink_to(outside_profile)

    profile = users / "steamuser"
    profile.mkdir()
    host_documents = tmp_path / "host-documents"
    host_documents.mkdir()
    nested_link = host_documents / "keep-link"
    nested_link.symlink_to(outside_target)
    (profile / "Documents").symlink_to(host_documents)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is True

    assert outside_link.is_symlink()
    assert nested_link.is_symlink()
    assert (users / "escaped").is_symlink()
    assert (profile / "Documents").is_dir()
    assert not (profile / "Documents").is_symlink()


def test_restores_link_when_directory_creation_fails(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    profile = prefix / "drive_c" / "users" / "steamuser"
    profile.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    desktop = profile / "Desktop"
    desktop.symlink_to(target)
    mkdir = wine_module.os.mkdir

    def fail_desktop(path, *args, **kwargs):
        if path == "Desktop":
            raise OSError
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(wine_module.os, "mkdir", fail_desktop)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is False

    assert desktop.is_symlink()
    assert os.readlink(desktop) == str(target)


def test_unlinks_public_profile_links(tmp_path):
    prefix = tmp_path / "prefix"
    public = prefix / "drive_c" / "users" / "Public"
    public.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    desktop = public / "Desktop"
    desktop.symlink_to(target)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is True

    assert desktop.is_dir()
    assert not desktop.is_symlink()


def test_rejects_symlinked_drive_c(tmp_path):
    prefix = tmp_path / "prefix"
    outside = tmp_path / "outside"
    profile = outside / "users" / "steamuser"
    profile.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    desktop = profile / "Desktop"
    desktop.symlink_to(target)
    prefix.mkdir()
    (prefix / "drive_c").symlink_to(outside)

    assert WineUtils.get_user_profile_ids(str(prefix)) is None
    assert WineUtils.unlink_user_profile_links(str(prefix)) is False
    assert desktop.is_symlink()


def test_does_not_delete_entry_replacing_scanned_link(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    profile = prefix / "drive_c" / "users" / "steamuser"
    profile.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    desktop = profile / "Desktop"
    desktop.symlink_to(target)
    rename = wine_module.os.rename
    replaced = False

    def replace_before_rename(src, dst, *args, **kwargs):
        nonlocal replaced
        if src == "Desktop" and not replaced:
            desktop.unlink()
            desktop.write_text("keep me")
            replaced = True
        return rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(wine_module.os, "rename", replace_before_rename)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is False
    assert desktop.is_file()
    assert desktop.read_text() == "keep me"


def test_continues_after_one_link_cannot_be_replaced(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    profile = prefix / "drive_c" / "users" / "steamuser"
    profile.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    desktop = profile / "Desktop"
    documents = profile / "Documents"
    desktop.symlink_to(target)
    documents.symlink_to(target)
    mkdir = wine_module.os.mkdir

    def fail_desktop(path, *args, **kwargs):
        if path == "Desktop":
            raise OSError
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(wine_module.os, "mkdir", fail_desktop)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is False
    assert desktop.is_symlink()
    assert documents.is_dir()
    assert not documents.is_symlink()


def test_rolls_back_when_backup_link_cannot_be_removed(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    profile = prefix / "drive_c" / "users" / "steamuser"
    profile.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    desktop = profile / "Desktop"
    desktop.symlink_to(target)
    unlink = wine_module.os.unlink

    def fail_backup(path, *args, **kwargs):
        if str(path).startswith(".bottles-link-"):
            raise OSError
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(wine_module.os, "unlink", fail_backup)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is False
    assert desktop.is_symlink()
    assert not list(profile.glob(".bottles-link-*"))


def test_discards_backup_link_when_replacement_directory_is_in_use(
    monkeypatch, tmp_path
):
    prefix = tmp_path / "prefix"
    profile = prefix / "drive_c" / "users" / "steamuser"
    profile.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    desktop = profile / "Desktop"
    desktop.symlink_to(target)
    unlink = wine_module.os.unlink
    failed_once = False

    def fail_first_backup(path, *args, **kwargs):
        nonlocal failed_once
        if str(path).startswith(".bottles-link-") and not failed_once:
            failed_once = True
            (desktop / "concurrent-file").write_text("keep me")
            raise OSError
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(wine_module.os, "unlink", fail_first_backup)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is False
    assert (desktop / "concurrent-file").read_text() == "keep me"
    assert not list(profile.glob(".bottles-link-*"))


def test_reports_failure_when_moved_link_disappears(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    profile = prefix / "drive_c" / "users" / "steamuser"
    profile.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    desktop = profile / "Desktop"
    desktop.symlink_to(target)
    mkdir = wine_module.os.mkdir

    def remove_backup_and_fail(path, *args, **kwargs):
        if path == "Desktop":
            backup = next(profile.glob(".bottles-link-*"))
            backup.unlink()
            raise OSError
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(wine_module.os, "mkdir", remove_backup_and_fail)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is False
    assert not desktop.exists()


def test_direct_link_failure_does_not_skip_nested_links(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    profile = prefix / "drive_c" / "users" / "steamuser"
    documents = profile / "Documents"
    documents.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    desktop = profile / "Desktop"
    music = documents / "My Music"
    desktop.symlink_to(target)
    music.symlink_to(target)
    mkdir = wine_module.os.mkdir

    def fail_desktop(path, *args, **kwargs):
        if path == "Desktop":
            raise OSError
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(wine_module.os, "mkdir", fail_desktop)

    assert WineUtils.unlink_user_profile_links(str(prefix)) is False
    assert desktop.is_symlink()
    assert music.is_dir()
    assert not music.is_symlink()


def test_rollback_does_not_overwrite_concurrent_entry(tmp_path):
    directory = tmp_path / "directory"
    directory.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    backup = directory / ".bottles-link-backup"
    backup.symlink_to(target)
    desktop = directory / "Desktop"
    desktop.write_text("concurrent data")
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)

    try:
        restored = WineUtils._restore_moved_entry(
            directory_fd,
            backup.name,
            desktop.name,
            discard_symlink_on_conflict=True,
        )
    finally:
        os.close(directory_fd)

    assert restored is False
    assert desktop.read_text() == "concurrent data"
    assert not backup.exists()


def test_conflicting_real_profiles_do_not_block_bottle_creation(tmp_path):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    (users / "mirko").mkdir(parents=True)
    (users / "steamuser").mkdir()

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is True
    assert not (users / "mirko").is_symlink()
    assert not (users / "steamuser").is_symlink()
