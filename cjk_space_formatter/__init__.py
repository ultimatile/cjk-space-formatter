"""CJK space formatter — remove unnecessary spaces between CJK and non-CJK characters."""

import re
from pathlib import Path

# Unicode ranges covering Japanese (Han, Hiragana, Katakana) and CJK punctuation
_CJK_RANGES = (
    r"\u3000-\u303f"  # CJK symbols and punctuation (、。「」 etc.)
    r"\u3040-\u309f"  # Hiragana
    r"\u30a0-\u30ff"  # Katakana
    r"\u4e00-\u9fff"  # CJK Unified Ideographs
    r"\uf900-\ufaff"  # CJK Compatibility Ideographs
    r"\uff01-\uff60"  # Fullwidth ASCII variants
    r"\uff65-\uff9f"  # Halfwidth Katakana
)
_CJK = f"[{_CJK_RANGES}]"

# CJK char followed by space(s) then non-space
_PAT_CJK_SPACE = re.compile(f"({_CJK}) +(?=\\S)")
# Non-space (except half-width colon and #) followed by space(s) then CJK char
_PAT_SPACE_CJK = re.compile(f"([^\\s:#]) +(?={_CJK})")
# Inline math: $...$
_PAT_INLINE_MATH = re.compile(r"\$[^$]*\$")
# Block math closer: just $ with optional Typst label
_PAT_BLOCK_MATH_CLOSE = re.compile(r"^\$\s*(<[\w-]+>)?\s*$")
# Typst structural prefixes whose trailing space must be preserved
_PAT_TYPST_PREFIX = re.compile(r"^(\s*(?:=+ |[-+] |\d+\. ))")
# Typst label references: @label followed by space(s) — space terminates the label
_PAT_TYPST_REF = re.compile(r"@[\w:.-]+ +")


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
    while i < n and depth > 0:
        c = text[i]
        if in_str:
            if c == '"':
                # Count consecutive backslashes immediately before this quote
                num_bs = 0
                j = i - 1
                while j >= 0 and text[j] == "\\":
                    num_bs += 1
                    j -= 1
                # Quote is escaped only when preceded by an odd number of backslashes
                if num_bs % 2 == 0:
                    in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    return i


def _extract_typst_hash(text: str) -> tuple[str, list[str]]:
    """Extract Typst hash expressions with trailing spaces into placeholders.

    Typst hash expressions start with ``#`` followed by a letter or underscore
    (distinguishing them from Markdown ``#123`` issue references).  The scanner
    walks through dot-separated identifiers and balanced parentheses (handling
    nested parens and quoted strings) so that inputs like
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


def _remove_cjk_spaces(text: str) -> str:
    """Remove spaces where one side is CJK and the other is non-whitespace."""
    text = _PAT_CJK_SPACE.sub(r"\1", text)
    text = _PAT_SPACE_CJK.sub(r"\1", text)
    return text


def format_line(line: str) -> str:
    """Format a single line, removing CJK-adjacent spaces outside math blocks."""
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

    # Extract inline math blocks into placeholders to protect their content
    math_blocks: list[str] = []

    def _save_math(m: re.Match) -> str:
        math_blocks.append(m.group(0))
        return f"\x00M{len(math_blocks) - 1}\x00"

    processed = _PAT_INLINE_MATH.sub(_save_math, line)

    # Extract Typst @references (with trailing space) to protect the space
    # that terminates the label from being removed
    ref_blocks: list[str] = []

    def _save_ref(m: re.Match) -> str:
        ref_blocks.append(m.group(0))
        return f"\x00R{len(ref_blocks) - 1}\x00"

    processed = _PAT_TYPST_REF.sub(_save_ref, processed)

    # Extract Typst hash expressions (with trailing space)
    processed, hash_blocks = _extract_typst_hash(processed)

    processed = _remove_cjk_spaces(processed)

    # Restore hash expressions, @references, then math blocks
    for i, block in enumerate(hash_blocks):
        processed = processed.replace(f"\x00H{i}\x00", block)
    for i, block in enumerate(ref_blocks):
        processed = processed.replace(f"\x00R{i}\x00", block)
    for i, block in enumerate(math_blocks):
        processed = processed.replace(f"\x00M{i}\x00", block)

    return prefix + processed + trailing


def format_text(text: str) -> str:
    """Format a complete text, handling block math detection across lines."""
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    in_block_math = False

    for line in lines:
        stripped = line.strip()

        if in_block_math:
            result.append(line)
            if _PAT_BLOCK_MATH_CLOSE.match(stripped):
                in_block_math = False
            continue

        # Block math: line starts with "$ " (single-line) or is just "$" (multi-line opener)
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
