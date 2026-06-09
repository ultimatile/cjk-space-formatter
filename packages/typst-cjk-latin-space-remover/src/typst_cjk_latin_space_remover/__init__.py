"""Remove CJK<->Latin/digit spaces in Typst markup, protecting Typst spans.

Typst-only front-end. Unlike the Markdown side (which delegates span detection to
a CommonMark parser), Typst has no context-dependent corner cases comparable to
CommonMark, so a sentinel-based regex scanner plus a line-level state machine
covers its protected spans: inline/block math `$`, inline/block raw `` ` ``,
`#expr`, `@ref`, and structural list/heading prefixes. The format-independent
CJK-Latin invariant is delegated to the shared core's `squash`.
"""

import re
from pathlib import Path

from ._core import CJK_CLASS, squash

_CJK = f"[{CJK_CLASS}]"

# Inline math: $...$
_PAT_INLINE_MATH = re.compile(r"\$[^$]*\$")
# Inline raw: `...` (single backtick, no embedded backtick). Multi-backtick
# inline raw is a documented non-goal. A block fence (>=3 backticks on its own
# line) is intercepted by the line state machine before reaching here.
_PAT_INLINE_RAW = re.compile(r"`[^`\n]+`")
# Block math closer: just $ with optional Typst label. Label characters mirror
# the `@ref` class (`[\w:.-]`): Typst labels routinely carry colons / dots, e.g.
# `<eq:fidelity>`, so a narrower class would fail to detect the close line and
# leave the rest of the file stuck inside the block-math state.
_PAT_BLOCK_MATH_CLOSE = re.compile(r"^\$\s*(<[\w:.-]+>)?\s*$")
# Block raw fence: a line whose first non-space content is a run of >=3 backticks.
_PAT_RAW_FENCE = re.compile(r"^\s*(`{3,})")
# Typst structural prefixes whose trailing space must be preserved (headings,
# bullets, ordered markers). Markdown `#` headings are out of scope here.
_PAT_TYPST_PREFIX = re.compile(r"^(\s*(?:=+ |[-+] |\d+\. ))")
# Typst label references: @label followed by space(s) — space terminates the label
_PAT_TYPST_REF = re.compile(r"@[\w:.-]+ +")
# Ordered-list markers ("1. ") preceding CJK, whose trailing space must be
# preserved. Recognised only at a structural position: line start, optionally
# behind Typst heading / bullet prefixes ("== 1. あ", "- 1. あ"). Anchoring to
# structure keeps prose numbers ("Fig. 1. 図"), versions ("v2. ") as plain text.
_PAT_ORDERED_MARKER = re.compile(rf"^\s*(?:(?:=+|[-+]) )*\d+\. +(?={_CJK})")

# Typst keywords that take a following expression (e.g. #set heading(...))
_TYPST_KEYWORDS = frozenset({"set", "show", "let", "import", "include"})


def _scan_ident(text: str, i: int, n: int) -> int:
    """Scan a dotted identifier: letters, digits, underscores, hyphens, dots."""
    while i < n and (text[i].isalnum() or text[i] in "_-."):
        i += 1
    return i


def _scan_balanced_parens(text: str, i: int, n: int) -> int:
    """Scan balanced parentheses, handling nesting and quoted strings.

    Inside quoted strings, a closing ``"`` is only recognised when preceded
    by an even number of backslashes (including zero).  This correctly
    handles paths like ``"C:\\\\"`` where ``\\\\`` is an escaped backslash
    and the following ``"`` genuinely closes the string.
    """
    if i >= n or text[i] != "(":
        return i
    depth = 1
    i += 1
    in_str = False
    bs_run = 0  # length of current consecutive-backslash run
    while i < n and depth > 0:
        c = text[i]
        if c == '"':
            if in_str:
                # Quote is escaped only when preceded by an odd number of backslashes
                if bs_run % 2 == 0:
                    in_str = False
            else:
                in_str = True
            bs_run = 0
        elif c == "\\":
            bs_run += 1
        else:
            bs_run = 0
            if not in_str:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
        i += 1
    return i


def _extract_typst_hash(text: str) -> tuple[str, list[str]]:
    """Extract Typst hash expressions with trailing spaces into placeholders.

    Typst hash expressions start with ``#`` followed by a letter or underscore.
    The scanner walks dot-separated identifiers and balanced parentheses
    (handling nested parens and quoted strings) so that inputs like
    ``#set heading(numbering: "1.") 見出し`` are fully captured.

    For Typst keywords (``set``, ``show``, etc.), the scanner continues past
    the space into the following identifier and its arguments.

    Only expressions followed by at least one space are extracted — the space
    terminates the expression in Typst and must be preserved.
    """
    blocks: list[str] = []
    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        # Typst hash expression: # followed by letter or underscore
        if (
            text[i] == "#"
            and i + 1 < n
            and (text[i + 1].isalpha() or text[i + 1] == "_")
        ):
            start = i
            i += 1
            ident_start = i
            i = _scan_ident(text, i, n)
            ident = text[ident_start:i]
            i = _scan_balanced_parens(text, i, n)

            # Typst keywords take a following expression: #set heading(...)
            if ident in _TYPST_KEYWORDS:
                while i < n and text[i] == " ":
                    i += 1
                i = _scan_ident(text, i, n)
                i = _scan_balanced_parens(text, i, n)

            # Capture trailing spaces
            space_start = i
            while i < n and text[i] == " ":
                i += 1
            if i > space_start:
                blocks.append(text[start:i])
                result.append(f"\x00H{len(blocks) - 1}\x00")
            else:
                result.append(text[start:i])
        else:
            result.append(text[i])
            i += 1

    return "".join(result), blocks


def format_line(line: str) -> str:
    """Format a single line, removing CJK-adjacent spaces outside protected spans."""
    trailing = ""
    if line.endswith("\n"):
        trailing = "\n"
        line = line[:-1]

    if not line.strip():
        return line + trailing

    # Preserve Typst structural prefixes (headings, list markers)
    prefix = ""
    prefix_match = _PAT_TYPST_PREFIX.match(line)
    if prefix_match:
        prefix = prefix_match.group(1)
        line = line[len(prefix) :]

    # Extract inline raw spans first so a `$` inside backticks is not mistaken
    # for math, and the run inside `code` is protected from squashing.
    raw_blocks: list[str] = []

    def _save_raw(m: re.Match) -> str:
        raw_blocks.append(m.group(0))
        return f"\x00C{len(raw_blocks) - 1}\x00"

    processed = _PAT_INLINE_RAW.sub(_save_raw, line)

    # Extract inline math blocks into placeholders to protect their content
    math_blocks: list[str] = []

    def _save_math(m: re.Match) -> str:
        math_blocks.append(m.group(0))
        return f"\x00M{len(math_blocks) - 1}\x00"

    processed = _PAT_INLINE_MATH.sub(_save_math, processed)

    # Extract Typst @references (with trailing space) to protect the space
    # that terminates the label from being removed
    ref_blocks: list[str] = []

    def _save_ref(m: re.Match) -> str:
        ref_blocks.append(m.group(0))
        return f"\x00R{len(ref_blocks) - 1}\x00"

    processed = _PAT_TYPST_REF.sub(_save_ref, processed)

    # Extract Typst hash expressions (with trailing space)
    processed, hash_blocks = _extract_typst_hash(processed)

    # Extract ordered-list markers (with trailing space) to protect the space
    # that separates the marker from following CJK text
    marker_blocks: list[str] = []

    def _save_marker(m: re.Match) -> str:
        marker_blocks.append(m.group(0))
        return f"\x00O{len(marker_blocks) - 1}\x00"

    processed = _PAT_ORDERED_MARKER.sub(_save_marker, processed)

    processed = squash(processed)

    # Restore every sentinel kind. Each placeholder is `\x00<letter><i>\x00` with
    # a distinct letter and `\x00` never occurs in restored content, so the kinds
    # are independent and the restore order does not affect the result.
    for i, block in enumerate(hash_blocks):
        processed = processed.replace(f"\x00H{i}\x00", block)
    for i, block in enumerate(marker_blocks):
        processed = processed.replace(f"\x00O{i}\x00", block)
    for i, block in enumerate(ref_blocks):
        processed = processed.replace(f"\x00R{i}\x00", block)
    for i, block in enumerate(math_blocks):
        processed = processed.replace(f"\x00M{i}\x00", block)
    for i, block in enumerate(raw_blocks):
        processed = processed.replace(f"\x00C{i}\x00", block)

    return prefix + processed + trailing


def format_text(text: str) -> str:
    """Format complete text, skipping block math and block raw regions.

    A line-level state machine keeps multi-line protected regions (block math
    `$ ... $`, block raw ``` ``` ... ``` ```) verbatim. Mirrors how the Markdown
    front-end gets the same protection structurally from its parser.
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    in_block_math = False
    in_block_raw = False
    raw_fence_len = 0

    for line in lines:
        stripped = line.strip()

        if in_block_raw:
            result.append(line)
            # Close on a line whose leading backtick run is at least as long as
            # the opening fence (Typst closes a raw block with matching backticks).
            m = _PAT_RAW_FENCE.match(line)
            if m and len(m.group(1)) >= raw_fence_len:
                in_block_raw = False
            continue

        if in_block_math:
            result.append(line)
            if _PAT_BLOCK_MATH_CLOSE.match(stripped):
                in_block_math = False
            continue

        # Block raw opener: a line starting with >=3 backticks. A self-contained
        # single-line raw (open and close on one line) stays verbatim without
        # toggling state.
        fence = _PAT_RAW_FENCE.match(line)
        if fence:
            result.append(line)
            fence_len = len(fence.group(1))
            rest = line[fence.end() :]
            if not re.search(rf"`{{{fence_len},}}", rest):
                in_block_raw = True
                raw_fence_len = fence_len
            continue

        # Block math: line is just "$" (multi-line opener) or "$ ... $" single-line
        if stripped == "$":
            result.append(line)
            in_block_math = True
            continue
        if stripped.startswith("$ ") and len(stripped) > 2:
            result.append(line)
            continue

        result.append(format_line(line))

    return "".join(result)


def format_file(path: Path, *, check: bool = False, in_place: bool = False) -> bool:
    """Format a file. Returns True if file was (or would be) changed."""
    content = path.read_text(encoding="utf-8")
    formatted = format_text(content)
    changed = content != formatted

    if changed and in_place:
        path.write_text(formatted, encoding="utf-8")

    return changed
