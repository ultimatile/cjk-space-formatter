"""mdformat plugin removing CJK<->Latin/digit spaces, math- and code-safe.

The plugin supplies only the CJK-Latin logic; mdformat + mdit-py-plugins supply
CommonMark correctness and math node-isation. Protection of fences, code spans,
escapes and run-length corner cases that plagued the old regex passes is "free"
here because the parser hands us those as opaque inline tokens — we never see
their interior, so we never touch it.

The core `squash` handles spaces *within* a plain text run. Spaces straddling a
text/protected-token boundary live on the text node's edge (the protected token
is a separate sibling), so they are folded here using the node's siblings.
"""

import re

from mdit_py_plugins.dollarmath import dollarmath_plugin

from ._core import CJK_CLASS, squash

_CJK = f"[{CJK_CLASS}]"
# CJK followed by trailing space(s) at a run's end — collapsed when the next
# sibling is a protected token (the space straddles the token boundary).
_TRAIL_CJK = re.compile(f"({_CJK}) +$")
# Leading space(s) before CJK at a run's start — collapsed when the previous
# sibling is a protected token.
_LEAD_CJK = re.compile(f"^ +(?={_CJK})")

# Inline tokens that are opaque protected spans: a CJK-adjacent space at the
# boundary with one of these collapses, exactly as if it abutted a non-space
# character. Fences and indented code never reach the `text` postprocessor at
# all — the parser keeps their content out of text nodes entirely.
_PROTECTED = {"code_inline", "math_inline", "math_block"}


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
    """Squash within the run, then fold spaces straddling protected boundaries."""
    out = squash(text)
    nxt = node.next_sibling
    if nxt is not None and nxt.type in _PROTECTED:
        m = _TRAIL_CJK.search(out)
        if m:
            out = out[: m.start() + 1]
    prv = node.previous_sibling
    if prv is not None and prv.type in _PROTECTED:
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
