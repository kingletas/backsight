# Every size is px, so the desktop's text scaling does nothing

## The bug

`requirements.md` asks the app to respect the system text scaling factor.
`typography.md` says to use px rather than pt in CSS, because pt is scaled a
second time on some setups. Both are right about what they are looking at, and
together they produce an app that ignores the setting completely.

Somebody who has set text scaling to 125% or 200% — which is the ordinary way to
make a desktop readable — sees no change in Backsight at all.

## The measurement

Two labels, identical text, one at `font-size: 13px` and one at `font-size: 1em`,
measured at the default DPI and again at twice it.

```
dpi 98304                    px-sized=  79  em-sized=  79
dpi 196608 (text scale 2x)   px-sized=  79  em-sized= 162
```

`gtk-xft-dpi` is what the text scaling factor moves. A px size does not follow
it. An em size follows it exactly once.

## What it costs today

Every size in the application is px. `TYPE` in `theme/tokens.py` is seven px
values, the zoom provider writes px, and the components stylesheet is px
throughout. The editor buffer has its own zoom, so a person can reach the code —
and nothing else in the window moves, including the eleven-point type the status
bar, the gutter and the rail metadata are set in, which is where it would matter
most.

## Fixed

`em` throughout. The design still lives in `TYPE` as px numbers, because
that is what a scale is; `tokens.ratio_of` turns one into a ratio of the body
size, and the body size is itself a ratio of the desktop's default so this
design's density survives somebody scaling their desktop up.

Seventeen px font sizes became ratios, and the buffer zoom with them — the zoom
is a deliberate choice about one buffer and the desktop factor is a deliberate
choice about everything, so they multiply.

Measured the same way it was found, at 2x:

```
class         1x    2x  follows scaling
tf-micro      62   120  True
tf-small      68   131  True
tf-strong     83   165  True
tf-title      99   200  True
```

A test refuses a px or pt font size in the stylesheet and refuses a ratio with
no token behind it, because the sheet now says the scale a second time.

## The shape of the fix

`em` satisfies both documents. It is scaled once, by the factor that is meant to
scale it, which is what `typography.md` was protecting against pt doing twice.
The scale becomes a set of ratios against the default font rather than seven
absolute numbers, and the ratios are the part that carries the design.

The editor buffer is the one place to think twice about: its size is a zoom
somebody set deliberately, and multiplying that by a desktop factor could take
it somewhere neither of them chose.


