# Finding 019 — `line-height` means something else in GTK, and `em` sizing meets the desktop

**Status: fixed and measured, 2026-09-10 — the row was 43% too tall for a reason nobody could see in the stylesheet.**

## The row was 23px where the design's arithmetic says 16

The design asks for code at 13.5px with **1.45 leading**, and calls the result
19.6px — the number its claim of *a quarter more code on screen* rests on.

Measured on a presented window, before this change: **23px**, every line.

## Why: GTK multiplies a different number

On the web `line-height: 1.45` multiplies the **font size**. GTK multiplies the
font's **natural line box** — ascent plus descent — which for JetBrains Mono is
already about 1.43 times its size. So the declaration compounded:

```
natural line 16px × 1.45 = 23.2 → 23px
```

**The stylesheet said exactly what the design said, and produced something
else.** No amount of reading `theme/__init__.py` would have shown it; it took
measuring `get_iter_location()` on two consecutive lines.

The row is now set in pixels by `app/leading.py`, from the font actually in
use, and `line-height` is gone from the buffer's stylesheet so only one thing
decides it.

| | Before | After |
|---|---:|---:|
| Code row | 23px | **16px** |
| Lines in a 700px buffer | 30 | **43** |

## Two traps inside the fix

**Measuring before the view is realised measures the wrong font.** The
stylesheet naming the family and the size is resolved at realisation, and even
`realize` itself is too early — the values haven't reached the Pango context
yet. It is set again on the idle after realisation, and a row computed in the
constructor was wrong by two pixels for the life of the page.

**A row can never be shorter than the glyphs in it.** The padding is clamped at
zero, so a leading below the font's own line box leaves the natural row rather
than clipping the text.

## The one that is not fixed: the font is 11.2px, not 13.5px

Every size in this application is a **ratio of the body size**, deliberately, so
that somebody who has set 150% text scaling for accessibility gets bigger code
too — a px font size doesn't follow that setting and an `em` one does.

The consequence is that **the design's pixel numbers only hold on a desktop
whose base font is 13px.** On this machine the base resolves to about 10.8px,
so `1.038em` of it renders at **11.176px** rather than 13.5.

That is a choice with a stated reason on both sides, and it is left alone:

- Going back to px would meet the design's number and **silently undo text
  scaling**, which is the defect finding 013 exists for.
- Keeping `em` means the design's absolute figures are a statement about a
  13px desktop, not about every desktop.

**What should change is the design guide**, which should say the sizes are
ratios of the desktop body size and give the pixel figures as *at a 13px base*.
A number that is only true on one machine reads as a measurement and is a
coincidence.
