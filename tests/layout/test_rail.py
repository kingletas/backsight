"""The rail: files, filtered in place, with the shape kept."""

from backsight.engine.layout.rail import (
    Entry,
    filtered,
    marked,
    quiet_prefixes,
    shared_prefix,
)


def tree() -> list[Entry]:
    return [
        Entry(name="envs/prod", depth=0, is_folder=True, key="envs/prod"),
        Entry(name="main.tf", depth=1, key="envs/prod/main.tf"),
        Entry(name="network.tf", depth=1, key="envs/prod/network.tf"),
        Entry(name="envs/staging", depth=0, is_folder=True, key="envs/staging"),
        Entry(name="main.tf", depth=1, key="envs/staging/main.tf"),
    ]


# --- what a row says about itself -----------------------------------------


def test_a_folder_says_it_is_one_on_the_side_a_reader_looks():
    assert Entry(name="network", is_folder=True).shown == "network/"
    assert Entry(name="network.tf").shown == "network.tf"


def test_the_shared_part_of_a_path_is_found_so_it_can_be_said_once():
    assert shared_prefix(["envs/prod", "envs/staging", "envs/dev"]) == "envs/"


def test_names_with_nothing_in_common_share_nothing():
    assert shared_prefix(["envs/prod", "platform/network"]) == ""


def test_one_name_on_its_own_is_not_a_group():
    assert shared_prefix(["envs/prod"]) == ""


def test_a_prefix_never_eats_the_last_segment_of_a_name():
    """A row with its own name removed says nothing at all, so the segment
    that differs always stays even when everything above it is common."""
    assert shared_prefix(["a/b/c", "a/b/d"]) == "a/b/"
    # One name being the whole of another's lead does not swallow either.
    found = quiet_prefixes(["a/b", "a/b/c"])
    assert found["a/b"] == "a/"
    assert found["a/b/c"] == "a/"


# --- filtering -------------------------------------------------------------


def test_an_empty_filter_is_the_whole_tree_and_hides_nothing():
    found = filtered(tree(), "")
    assert len(found.entries) == 5
    assert found.hidden == 0
    assert not found.is_filtered


def test_a_match_keeps_the_module_it_is_in():
    """A file shown without its module is a search result, not a tree."""
    found = filtered(tree(), "network")
    assert [one.key for one in found.entries] == ["envs/prod", "envs/prod/network.tf"]


def test_it_says_how_much_of_the_tree_is_being_shown():
    assert filtered(tree(), "network").summary() == "1 module · 1 file"


def test_nothing_hidden_says_nothing():
    assert filtered(tree(), "").summary() == ""


def test_a_module_that_matches_brings_its_files_with_it():
    found = filtered(tree(), "staging")
    assert [one.key for one in found.entries] == ["envs/staging", "envs/staging/main.tf"]


def test_a_filter_that_matches_nothing_shows_nothing_rather_than_everything():
    found = filtered(tree(), "zzzz")
    assert found.entries == []
    assert found.hidden == 5


def test_matching_is_fuzzy_rather_than_exact():
    assert [one.key for one in filtered(tree(), "ntwk").entries] == [
        "envs/prod",
        "envs/prod/network.tf",
    ]


# --- marking ---------------------------------------------------------------


def test_the_matched_letters_are_reported_so_they_can_be_marked():
    assert marked("main.tf", "mai") == ((0, 3),)


def test_letters_apart_are_separate_marks():
    """Leftmost first: the `t` of `network` is the second letter matched, not
    the one in the extension."""
    assert marked("network.tf", "ntf") == ((0, 1), (2, 3), (9, 10))


def test_a_name_that_does_not_match_is_reported_as_no_match_rather_than_none_found():
    assert marked("main.tf", "zzz") is None


def test_matching_ignores_case():
    assert marked("Main.tf", "main") == ((0, 4),)


# --- what a real repository looks like -------------------------------------
#
# `~/Development/terraform` — 27 root modules under two folders, 63 modules in
# all, 273 files. Every rule below was written after driving the application
# against it, because the fixtures in this repository are small enough that
# none of these failed on them.


def a_real_shape() -> list[str]:
    """Eleven roots under `examples/` and sixteen under `modules/`."""
    return [
        *(f"examples/{name}" for name in ("account-baseline", "magento", "network-hub")),
        *(f"modules/{name}" for name in ("alb", "context", "vpc-peering")),
    ]


def test_two_groups_each_get_their_own_quiet_prefix():
    """A single prefix over all of them is the empty string, so every row was
    drawn in full ink and the eight characters they had in common were the
    loudest thing in the rail."""
    found = quiet_prefixes(a_real_shape())
    assert found["examples/magento"] == "examples/"
    assert found["modules/alb"] == "modules/"


def test_the_old_single_answer_is_nothing_for_two_groups():
    """Which is exactly what it should say, and why the rail stopped asking."""
    assert shared_prefix(a_real_shape()) == ""


def test_a_name_with_no_family_keeps_all_of_itself():
    assert quiet_prefixes(["envs/prod", "envs/dev", "main"])["main"] == ""


def test_the_deepest_shared_run_wins():
    found = quiet_prefixes(["a/b/c/one", "a/b/c/two", "a/z/three"])
    assert found["a/b/c/one"] == "a/b/c/"
    assert found["a/z/three"] == "a/"


def test_what_is_shown_is_counted_rather_than_what_is_hidden():
    """ "318 hidden" was accurate and useless: it counted every file in every
    collapsed module, so it was larger than the number of rows a reader could
    see it against."""
    said = filtered(tree(), "network")
    assert said.summary() == "1 module · 1 file"


def test_it_says_modules_and_files_in_the_plural_where_they_are():
    entries = [
        Entry(name="envs/a", depth=0, is_folder=True, key="a"),
        Entry(name="main.tf", depth=1, key="a/main.tf"),
        Entry(name="other.tf", depth=1, key="a/other.tf"),
        Entry(name="envs/b", depth=0, is_folder=True, key="b"),
        Entry(name="main.tf", depth=1, key="b/main.tf"),
    ]
    assert filtered(entries, "main").summary() == "2 modules · 2 files"
