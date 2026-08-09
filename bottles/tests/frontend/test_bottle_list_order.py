from types import SimpleNamespace

import pytest
from gi.repository import Gio

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.views.list import (  # noqa: E402
    BottleView,
    _bottle_order_id,
    _ordered_bottles,
    _replace_group_order,
)


def _config(path, environment="Gaming"):
    return SimpleNamespace(Path=path, Environment=environment)


def test_ordered_bottles_keeps_new_bottles_at_the_end():
    alpha = _config("Alpha")
    beta = _config("Beta")
    gamma = _config("Gamma")

    ordered = _ordered_bottles(
        [alpha, beta, gamma],
        [_bottle_order_id(beta), _bottle_order_id(alpha)],
    )

    assert [config.Path for config in ordered] == ["Beta", "Alpha", "Gamma"]


def test_replace_group_order_keeps_unavailable_and_other_group_entries():
    configured = [
        "bottle:Alpha",
        "bottle:Unavailable",
        "steam:/steam/one",
        "bottle:Beta",
    ]

    result = _replace_group_order(
        configured,
        ["bottle:Alpha", "bottle:Beta", "bottle:Gamma"],
        ["bottle:Gamma", "bottle:Beta", "bottle:Alpha"],
    )

    assert result == [
        "bottle:Gamma",
        "bottle:Unavailable",
        "steam:/steam/one",
        "bottle:Beta",
        "bottle:Alpha",
    ]


def test_reorder_bottle_updates_only_its_group():
    alpha = _config("Alpha")
    beta = _config("Beta")
    steam = _config("/steam/one", "Steam")
    configured = [
        _bottle_order_id(alpha),
        _bottle_order_id(steam),
        _bottle_order_id(beta),
    ]
    saved = []
    refreshes = []
    settings = SimpleNamespace(
        get_strv=lambda _key: configured,
        set_strv=lambda _key, value: saved.extend(value),
    )
    view = SimpleNamespace(
        window=SimpleNamespace(
            settings=settings,
            manager=SimpleNamespace(
                local_bottles={
                    "Alpha": alpha,
                    "Beta": beta,
                    "Steam": steam,
                }
            ),
        ),
        update_bottles_list=lambda **kwargs: refreshes.append(kwargs),
    )

    BottleView._BottleView__reorder_bottle(view, SimpleNamespace(config=beta), "top")

    assert saved == [
        _bottle_order_id(beta),
        _bottle_order_id(steam),
        _bottle_order_id(alpha),
    ]
    assert refreshes == [{"refresh_updates": False}]


@pytest.mark.parametrize(
    ("titles", "terms", "expected"),
    [
        ([], "", (False, True, False)),
        (["Alpha"], "alpha", (True, False, False)),
        (["Alpha"], "missing", (False, False, True)),
    ],
)
def test_bottle_list_empty_state(titles, terms, expected):
    visible = {}

    def widget(name):
        return SimpleNamespace(
            set_visible=lambda value: visible.__setitem__(name, value)
        )

    view = SimpleNamespace(
        _BottleView__bottles={
            title: SimpleNamespace(get_title=lambda title=title: title)
            for title in titles
        },
        _BottleView__filter_bottles=BottleView._BottleView__filter_bottles,
        pref_page=widget("list"),
        bottle_status=widget("empty"),
        no_bottles_found=widget("no-results"),
        umu_provider=SimpleNamespace(available=False),
    )

    BottleView._BottleView__update_empty_state(view, terms)

    assert (
        visible["list"],
        visible["empty"],
        visible["no-results"],
    ) == expected


def test_umu_actions_replace_empty_state():
    visible = {}

    def widget(name):
        return SimpleNamespace(
            set_visible=lambda value: visible.__setitem__(name, value)
        )

    view = SimpleNamespace(
        _BottleView__bottles={},
        _BottleView__filter_bottles=BottleView._BottleView__filter_bottles,
        pref_page=widget("list"),
        bottle_status=widget("empty"),
        no_bottles_found=widget("no-results"),
        umu_provider=SimpleNamespace(available=True),
    )

    BottleView._BottleView__update_empty_state(view, "")

    assert visible == {"list": True, "empty": False, "no-results": False}


def test_search_updates_filters_and_empty_state():
    filters = []
    empty_states = []
    filter_bottles = BottleView._BottleView__filter_bottles
    bottle_list = SimpleNamespace(
        set_filter_func=lambda callback, terms: filters.append((callback, terms))
    )
    view = SimpleNamespace(
        _BottleView__filter_bottles=filter_bottles,
        _BottleView__update_empty_state=empty_states.append,
        list_bottles=bottle_list,
        list_umu=bottle_list,
        list_steam=bottle_list,
    )

    BottleView._BottleView__search_bottles(
        view, SimpleNamespace(get_text=lambda: "missing")
    )

    assert filters == [
        (filter_bottles, "missing"),
        (filter_bottles, "missing"),
        (filter_bottles, "missing"),
    ]
    assert empty_states == ["missing"]
