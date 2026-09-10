"""The editor's own colours, generated from the same tokens as everything else.

A hand-written scheme drifts from the palette the moment either changes, and
the design system's whole premise is one source of truth. So the scheme is
generated: `python -m backsight.app.theme.schemes` writes both files.

The interpolation colour is the one place the editor departs from the four
consequence levels — an interpolation is neither safe nor dangerous, it is a
different *kind* of thing, and the palette gives it `syn_interp` for that.
"""

from __future__ import annotations

from pathlib import Path

from backsight.app.theme import tokens

HERE = Path(__file__).parent
SCHEMES = HERE / "schemes"

NAMES = {"light": "Backsight Light", "dark": "Backsight Dark"}


def scheme(mode: str) -> str:
    """One GtkSourceView style scheme, as XML."""
    palette = tokens.DARK if mode == "dark" else tokens.LIGHT
    over = "#FFFFFF" if mode == "dark" else palette["ink"]
    colours = {
        "bg": palette["panel"],
        "fg": palette["ink"],
        "dim": palette["ink_faint"],
        # Washes, flattened. A scheme takes a solid value, and these are the
        # same three the stylesheet draws with alpha — see tokens.blend.
        "selection": tokens.blend(palette["accent_fill"], palette["panel"], 0.22),
        "line": tokens.blend(over, palette["panel"], 0.035 if mode == "light" else 0.05),
        "bracket": tokens.blend(palette["accent_edge"], palette["panel"], 0.35),
        # Eleven syntax tokens. The block keyword, the provider's word for the
        # type, and the name you chose are three different kinds of thing, and
        # reading HCL is mostly telling them apart.
        "block": palette["syn_block"],
        "type": palette["syn_type"],
        "name": palette["syn_name"],
        "attr": palette["syn_attr"],
        "string": palette["syn_string"],
        "number": palette["syn_number"],
        "fn": palette["syn_fn"],
        "ref": palette["syn_ref"],
        "interp": palette["syn_interp"],
        "comment": palette["syn_comment"],
        "operator": palette["syn_operator"],
        "invalid": palette["syn_invalid"],
        "create": palette["plan_create"],
        "update": palette["plan_update"],
        "replace": palette["plan_replace"],
        "destroy": palette["plan_destroy"],
    }
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!--",
        "  Generated from backsight/app/theme/tokens.py. Do not edit.",
        "  Regenerate with: python -m backsight.app.theme.schemes",
        "",
        "  The one thing to keep: block-title is the resource *type* and",
        "  block-label is its *name*. They are different things and must not",
        "  share a colour.",
        "-->",
        f'<style-scheme id="backsight-{mode}" name="{NAMES[mode]}" version="1.0">',
        "  <author>Backsight</author>",
        f"  <description>Generated from the design tokens — {mode}.</description>",
        "",
    ]
    for name, value in colours.items():
        lines.append(f'  <color name="{name}" value="{value}"/>')

    lines += [
        "",
        "  <!-- Canvas -->",
        '  <style name="text"                 foreground="fg" background="bg"/>',
        '  <style name="selection"            background="selection"/>',
        '  <style name="current-line"         background="line"/>',
        '  <style name="search-match"         background="selection" foreground="fg"/>',
        "  <!-- A tinted fill rather than a box: a box adds two more vertical",
        "       lines to a screen already full of them. -->",
        '  <style name="bracket-match"        background="bracket"/>',
        '  <style name="bracket-mismatch"     foreground="invalid" bold="true"/>',
        '  <style name="cursor"               foreground="fg"/>',
        '  <style name="line-numbers"         foreground="dim" background="bg"/>',
        "  <!-- The caret line's own number goes to full ink. With the wash",
        "       above it, that is how somebody finds the caret after looking",
        "       away, and it costs nothing to draw. -->",
        '  <style name="current-line-number"  foreground="fg" background="line" bold="true"/>',
        '  <style name="right-margin"         foreground="dim" background="dim"/>',
        '  <style name="draw-spaces"          foreground="dim"/>',
        '  <style name="background-pattern"   background="line"/>',
        "",
        "  <!-- Syntax -->",
        '  <style name="def:keyword"          foreground="block" bold="true"/>',
        '  <style name="def:type"             foreground="type"/>',
        '  <style name="def:string"           foreground="string"/>',
        '  <style name="def:number"           foreground="number"/>',
        '  <style name="def:boolean"          foreground="number"/>',
        '  <style name="def:constant"         foreground="number"/>',
        '  <style name="def:special-constant" foreground="ref"/>',
        '  <style name="def:comment"          foreground="comment" italic="true"/>',
        '  <style name="def:function"         foreground="fn"/>',
        '  <style name="def:identifier"       foreground="attr"/>',
        '  <style name="def:special-char"     foreground="interp"/>',
        '  <style name="def:operator"         foreground="operator"/>',
        '  <style name="def:error"            foreground="invalid" bold="true"/>',
        '  <style name="def:note"             foreground="update" bold="true"/>',
        '  <style name="def:preprocessor"     foreground="block"/>',
        '  <style name="def:statement"        foreground="block"/>',
        '  <style name="def:strong-emphasis"  foreground="block" bold="true"/>',
        "",
        "  <!-- HCL. Three colours on one line, because `resource`, the",
        "       provider's `aws_instance` and your own `api` are three",
        "       different kinds of thing. -->",
        '  <style name="terraform:block-type"       foreground="block" bold="true"/>',
        '  <style name="terraform:block-title"      foreground="type"/>',
        '  <style name="terraform:block-label"      foreground="name"/>',
        '  <style name="terraform:keyword"          foreground="block" bold="true"/>',
        '  <style name="terraform:statement"        foreground="block"/>',
        "  <!-- An attribute name, on the left of an `=` and after a `.`. -->",
        '  <style name="terraform:identifier"       foreground="attr"/>',
        '  <style name="terraform:reference"        foreground="ref"/>',
        '  <style name="terraform:builtin-function" foreground="fn"/>',
        '  <style name="terraform:data-type"        foreground="type"/>',
        '  <style name="terraform:string"           foreground="string"/>',
        '  <style name="terraform:number"           foreground="number"/>',
        '  <style name="terraform:boolean"          foreground="number"/>',
        '  <style name="terraform:null"             foreground="number"/>',
        '  <style name="terraform:comment"          foreground="comment" italic="true"/>',
        "  <!-- The delimiters are marked; what is inside them is an",
        "       expression and keeps the colours an expression has. -->",
        '  <style name="terraform:interpolation"    foreground="interp" bold="true"/>',
        '  <style name="terraform:interpolated"     foreground="fg"/>',
        '  <style name="terraform:escaped-character" foreground="interp"/>',
        '  <style name="terraform:error"            foreground="invalid" bold="true"/>',
        "",
        "  <!-- Diff, here so it cannot drift from the syntax palette. -->",
        '  <style name="diff:added-line"      foreground="create"/>',
        '  <style name="diff:removed-line"    foreground="destroy"/>',
        '  <style name="diff:changed-line"    foreground="update"/>',
        '  <style name="diff:location"        foreground="dim"/>',
        "</style-scheme>",
        "",
    ]
    return "\n".join(lines)


def write(directory: Path | None = None) -> list[Path]:
    tokens.check_parity()
    where = Path(directory or SCHEMES)
    where.mkdir(parents=True, exist_ok=True)
    written = []
    for mode in ("light", "dark"):
        path = where / f"backsight-{mode}.xml"
        path.write_text(scheme(mode), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for path in write():
        print("wrote", path)
