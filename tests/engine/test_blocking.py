"""What stops a workspace being useful, and which one to say first."""

from __future__ import annotations

from backsight.engine.layout.blocking import BANNERS, LOCAL_STATE, Blocker, first


def test_nothing_wrong_is_no_banner():
    assert first(engine_missing=False, initialised=True, has_backend=True) is None


def test_the_engine_comes_before_everything():
    """Nothing else can be acted on while it is missing."""
    found = first(engine_missing=True, initialised=False, has_backend=False)
    assert found.blocker is Blocker.NO_ENGINE


def test_init_is_the_last_banner_there_is():
    found = first(engine_missing=False, initialised=False, has_backend=False)
    assert found.blocker is Blocker.NOT_INITIALISED


def test_one_at_a_time():
    """Two banners is a person choosing which to read, and the first is the
    only one they can act on anyway."""
    found = first(engine_missing=True, initialised=False, has_backend=False)
    assert found is not None
    assert isinstance(found, type(BANNERS[Blocker.NO_ENGINE]))


def test_every_one_says_what_is_wrong_what_it_prevents_and_what_to_do():
    for banner in BANNERS.values():
        assert banner.title
        assert banner.body
        assert banner.action
        assert banner.command
        assert banner.icon


def test_initialisation_cannot_be_dismissed():
    """Dismissing it would hide the reason nothing works."""
    assert not BANNERS[Blocker.NOT_INITIALISED].dismissible
    assert not BANNERS[Blocker.NO_ENGINE].dismissible


def test_local_state_is_not_a_banner_at_all():
    """**A banner is for something nothing works without.** Local state stops
    nothing: it is true on open, true all day, and true of every module in a
    repository that is a library rather than a deployment — twenty-seven of
    them in one real one, none with a backend.

    A hundred and ten pixels across the top of the window for that is dismissed
    on reflex, and the banner that matters is dismissed on the same reflex a
    week later. It is a fact in the verdict line instead."""
    assert first(engine_missing=False, initialised=True, has_backend=False) is None
    assert Blocker.NO_BACKEND not in BANNERS
    assert LOCAL_STATE == "local state"


def test_none_of_them_says_please():
    for banner in BANNERS.values():
        said = f"{banner.title} {banner.body} {banner.action}".lower()
        for word in ("please", "simply", "just ", "easy", "successfully"):
            assert word not in said, banner.title


def test_a_banner_says_roughly_how_long_the_fix_takes_where_it_can():
    assert "twenty seconds" in BANNERS[Blocker.NOT_INITIALISED].body
