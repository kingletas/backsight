# Acceptance and regression

Two suites, and they answer different questions.

**`tests/acceptance/`** drives a real window on a private display and asks what
is **on screen**. It exists because the unit suite was 1,856 tests green while
the editor drew nothing at all: every component worked and the route to it did
not.

The check a unit test cannot make is in `looking.drawn` — a widget can be
visible, hold the right text, pass every assertion about its state, and be zero
pixels wide. That is what happened.

**`tests/regression/`** is one test per defect that actually shipped. Not
hypothetical failures: the ones this codebase produced, each named for what
somebody would have seen rather than for the code that was wrong. Every one of
them was green in the unit suite at the time.

## Both directions, every time

A test that has only ever been seen passing has not been tested. Each defect
here was **put back** and the suite watched go red before the test was kept:

| Defect put back | What went red |
|---|---|
| Inspector width divided before layout | `test_the_editor_has_room_to_be_seen` |
| Return in the library search not wired | `test_return_puts_the_best_match_in_the_file`, and the tab-stop one |
| Unscrolled drawer switcher | **nothing** — see below |

The third row is why this table is here. The drawer's tabs were visibly clipped
and scrolling them is a real fix, but putting the defect back turned nothing
red: it was not what pushed the inspector off screen, and the test that claimed
to catch it now says so instead.

## Running them

```
make acceptance
```

They are slower than unit tests by an order of magnitude, and worth every
second. `make check` runs them.
