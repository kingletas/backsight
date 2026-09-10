# 003 — The accent is pinned, and 002 is narrowed to everything else

**Decided 2026-09-09. Supersedes the accent clause of [002](002-colour-splits-between-the-desktop-and-us.md); the rest of 002 stands.**

## What was chosen

**The accent is pinned in both schemes**, alongside the four consequence
colours. Window, view, header bar, sidebar, borders and text still come from
libadwaita's named colours, which is what 002 is about and what it got right.

`Follow the desktop accent` stays available as a preference, off by default.

## Why the accent is different from the rest of the chrome

**Backsight's accent sits one pixel from four pinned severity colours.** On the
machine this was built on the desktop accent is a red — so the primary action,
the current file, the selection and every plan identifier were drawn in the
same hue as *destroy*.

That is not a question of taste. It is a person reading a plan and being unable
to tell the thing that is safe to press from the thing that is not, because
their desktop happens to be red.

002's reasoning — *follow the desktop* — is right about everything that carries
no meaning. The accent carries meaning here in a way it does not in a text
editor or a mail client: it is the colour that says **this is not a severity**,
and it can only say that while it is distinguishable from all four of them.

## What the code was already doing

**Pinning.** `tokens.py` has pinned `accent_text`, `accent_bg`, `accent_edge`
and `accent_fill` since it was written, and `ADWAITA_MAP` repoints libadwaita's
own `accent_bg_color` at the pinned value — the opposite direction to what 002
describes.

So this record does not change behaviour. It makes the record agree with the
code, which is the point: **a decision record and its code disagreeing is worse
than either answer**, because the next person has no way to tell which one is
out of date.

## What else was considered

**Following the desktop and warning when the accent collides with a severity.**
Rejected as the default and kept as the preference: a warning that fires on a
red or orange desktop and cannot be acted on except by changing the desktop is
a warning nobody can clear. It is worth having for somebody who has deliberately
turned the preference on.

**Choosing an accent by rotating away from the desktop's.** Rejected: an accent
that moves is one nobody can describe, and every screenshot, guide and bug
report would be about a different colour.
