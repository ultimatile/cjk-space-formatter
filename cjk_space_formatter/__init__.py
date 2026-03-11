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
# Non-space followed by space(s) then CJK char
_PAT_SPACE_CJK = re.compile(f"(\\S) +(?={_CJK})")
# Inline math: $...$
_PAT_INLINE_MATH = re.compile(r"\$[^$]*\$")
# Block math closer: just $ with optional Typst label
_PAT_BLOCK_MATH_CLOSE = re.compile(r"^\$\s*(<[\w-]+>)?\s*$")
# Typst structural prefixes whose trailing space must be preserved
_PAT_TYPST_PREFIX = re.compile(r"^(\s*(?:=+ |[-+] |\d+\. ))")


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
    processed = _remove_cjk_spaces(processed)

    # Restore math blocks
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
