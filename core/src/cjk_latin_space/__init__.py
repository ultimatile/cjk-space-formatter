"""cjk-latin-space core.

Single source of the format-independent invariant shared by every front-end:
within one *plain run* of text (no protected spans — no math, code, refs), a run
of spaces *between* two non-space characters is removed when either side is CJK
(so CJK<->Latin, CJK<->digit and CJK<->CJK all collapse), with one exception — a
space immediately following the half-width colon is kept as correct prose
typography. Leading and trailing whitespace has nothing on its far side and so
is left alone; front-ends own their own edges.

Boundaries with protected spans (math/code/refs) are deliberately NOT handled
here — that plumbing lives in each front-end, which knows its own parser's span
model. The CJK character class is exported so that plumbing's boundary logic
shares one definition with `squash` and cannot drift from it.
"""

import re

# Unicode ranges covering Japanese (Han, Hiragana, Katakana) and CJK punctuation.
# Exported as a raw character-class body (no enclosing brackets) so front-ends
# can splice it into their own boundary patterns against the same definition.
CJK_CLASS = (
    r"　-〿"  # CJK symbols and punctuation (、。「」 etc.)
    r"぀-ゟ"  # Hiragana
    r"゠-ヿ"  # Katakana
    r"一-鿿"  # CJK Unified Ideographs
    r"豈-﫿"  # CJK Compatibility Ideographs
    r"！-｠"  # Fullwidth ASCII variants
    r"･-ﾟ"  # Halfwidth Katakana
)
_CJK = f"[{CJK_CLASS}]"

# CJK char followed by space(s) then a non-space character.
_CJK_SPACE = re.compile(f"({_CJK}) +(?=\\S)")
# Non-space (except the half-width colon) followed by space(s) then a CJK char.
# The colon is preserved because "注: これは" is correct prose typography.
_SPACE_CJK = re.compile(f"([^\\s:]) +(?={_CJK})")


def squash(plain_run: str) -> str:
    """Collapse spaces adjacent to CJK characters within one plain run.

    A run of spaces is removed when a CJK character sits on either side of it,
    so CJK<->Latin, CJK<->digit and CJK<->CJK boundaries all collapse; the lone
    exception is a space immediately following a half-width colon (kept as
    correct prose typography). The input must contain no protected spans:
    callers strip math/code/refs first. string -> string, target-independent;
    all syntax-specific exceptions belong to the front-end, not here.
    """
    plain_run = _CJK_SPACE.sub(r"\1", plain_run)
    plain_run = _SPACE_CJK.sub(r"\1", plain_run)
    return plain_run


__all__ = ["CJK_CLASS", "squash"]
