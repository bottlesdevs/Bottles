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

    assert WineUtils.ensure_user_profile_alias(str(prefix), "mirko") is False

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
