"""mdformat plugin removing CJK<->Latin/digit spaces, math- and code-safe.

The plugin supplies only the CJK-Latin logic; mdformat + mdit-py-plugins supply
CommonMark correctness and math node-isation. Protection of fences, code spans,
escapes and run-length corner cases that plagued the old regex passes is "free"
here because the parser hands us those as opaque inline tokens — we never see
their interior, so we never touch it.

That protection reaches exactly as far as the enabled extension set. A construct
no enabled extension parses arrives as ordinary paragraph text, and a space that
construct uses as a *delimiter* is then indistinguishable from prose spacing.
`mdformat-gfm` is a hard dependency because it closes that hole for GFM task
lists, autolink literals and tables; constructs from dialects nothing here
parses stay exposed. The dependency only makes `gfm` and `tables` available,
though: a caller that narrows the extension set (the `extensions=` argument,
`--extensions`, or `.mdformat.toml`) must name them alongside this plugin, or
even those constructs lose their protection again.

The core `squash` handles spaces *within* a plain text run. A space straddling
the boundary between a text run and an adjacent inline node lives on the text
node's edge (the node is a separate sibling), so it is folded here using the
node's siblings — see `_folds_across` for which siblings a boundary space
collapses across and the one emphasis case it must not.
"""

import re

from mdit_py_plugins.dollarmath import dollarmath_plugin

from ._core import CJK_CLASS, squash

_CJK = f"[{CJK_CLASS}]"
# CJK followed by trailing space(s) at a run's end — collapsed when the next
# sibling is a node a boundary space folds across (see `_folds_across`).
_TRAIL_CJK = re.compile(f"({_CJK}) +$")
# Leading space(s) before CJK at a run's start — collapsed when the previous
# sibling folds (see `_folds_across`).
_LEAD_CJK = re.compile(f"^ +(?={_CJK})")

# Opaque protected spans: a CJK-adjacent boundary space collapses across one of
# these exactly as if it abutted a non-space character. Fences and indented code
# never reach the `text` postprocessor at all — the parser keeps their content
# out of text nodes entirely.
_PROTECTED = {"code_inline", "math_inline", "math_block"}
# Transparent inline containers a boundary space also folds across: links,
# images and strikethrough carry no intraword restriction, so dropping the space
# is always safe. Strikethrough belongs here rather than with the conditional
# emphasis below because GFM places no such restriction on `~~`.
_TRANSPARENT = {"link", "image", "s"}
# Emphasis is conditional. CommonMark forbids `_`/`__` from opening or closing
# intraword, and CJK count as word characters, so folding a space around
# underscore emphasis would turn the markers literal (日本語 _x_ -> 日本語_x_
# renders the underscores). Asterisk emphasis has no such restriction; mdformat
# preserves the source marker, so a folded `*`/`**` stays valid on output.
_EMPHASIS = {"em", "strong"}


def _folds_across(sibling) -> bool:
    """Whether a CJK-adjacent boundary space collapses across this sibling."""
    if sibling.type in _PROTECTED or sibling.type in _TRANSPARENT:
        return True
    if sibling.type in _EMPHASIS:
        return bool(sibling.markup) and all(c == "*" for c in sibling.markup)
    return False


def update_mdit(mdit):
    """Enable dollarmath so `$...$` / `$$...$$` become protected math nodes."""
    mdit.use(dollarmath_plugin)


def _render_math_inline(node, context):
    return f"${node.content}$"


def _render_math_block(node, context):
    # node.content carries the math body with surrounding newlines; strip the
    # outer ones so the fence is not padded with blank lines on re-render.
    return f"$$\n{node.content.strip(chr(10))}\n$$"


def _text_postprocess(text, node, context):
    """Squash within the run, then fold spaces straddling a foldable boundary."""
    out = squash(text)
    nxt = node.next_sibling
    if nxt is not None and _folds_across(nxt):
        m = _TRAIL_CJK.search(out)
        if m:
            out = out[: m.start() + 1]
    prv = node.previous_sibling
    if prv is not None and _folds_across(prv):
        out = _LEAD_CJK.sub("", out)
    return out


RENDERERS = {
    "math_inline": _render_math_inline,
    "math_block": _render_math_block,
}
POSTPROCESSORS = {"text": _text_postprocess}

# Required: this plugin deliberately changes rendered HTML (removing spaces),
# so mdformat's is_md_equal safety check would otherwise silently discard every
# change and the plugin would be a no-op. Declaring intent opts out of that check.
CHANGES_AST = True
