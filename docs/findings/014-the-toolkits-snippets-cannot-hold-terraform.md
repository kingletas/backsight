# The toolkit's snippet engine cannot hold Terraform

GtkSourceView 5 has a complete snippet implementation — `Snippet.new_parsed`,
`View.push_snippet`, tab stops, focus navigation. It looked like the whole
foundation for a snippet library, and it cannot be used for HCL.

## Why

Its placeholder syntax is `${1:default}`. HCL's interpolation syntax is
`${var.environment}`. The parser consumes the opening brace of anything after a
`$`, so every interpolation in a stored snippet arrives corrupted.

Measured, with the text handed to `Snippet.new_parsed` and read back out of the
buffer after `push_snippet`:

```
raw                    '${var.environment}'      -> '$var.environment}'
backslash-dollar       '\${var.environment}'     -> '$var.environment}'
double-dollar          '$${var.environment}'     -> '$var.environment}'
backslash-brace        '$\{var.environment}'     -> '{var.environment}'
dollar-escaped-brace   '\$\{var.environment}'    -> '{var.environment}'
```

No escape round-trips. There is no form of `${var.environment}` that survives.

Most real Terraform contains interpolation — `"${var.environment}-logs"`,
`"web-${count.index}"`, `"${aws_s3_bucket.this.id}"` — so this is not an edge
case to work around. It is the ordinary content.

## What is done instead

Tab stops are ours. A body is stored as plain HCL with placeholders written
`${1}` or `${1:default}`, and **a digit immediately after `${` is what makes it
a placeholder** — an HCL identifier cannot begin with a digit, so the two are
unambiguous by construction, and the syntax stays the one everybody already
knows from every other editor.

The one thing it cannot express is a literal `${1}` in HCL, which interpolates
the number one. Nobody writes that.

Placement is `Gtk.TextMark`s left at each stop and a key controller that moves
between them while a snippet is live. Marks move with the text as it is edited,
which is the property that makes this work at all.

## What is kept from the toolkit

Nothing of the snippet engine. `GtkSource.Snippet` is not imported anywhere.
Saying so here because it exists, it is the obvious choice, and the next person
to look will reach for it first.
