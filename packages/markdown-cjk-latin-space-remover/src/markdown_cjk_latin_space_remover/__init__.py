"""Remove spaces next to CJK characters in Markdown by deleting U+0020 bytes.

pyromark (pulldown-cmark) supplies byte ranges; the output is the input with
some spaces deleted and is not re-rendered. The shared core's `squash` picks the
spaces inside a run of prose; this module builds the runs, adds the spaces at a
run's edge next to a foldable construct, and drops deletions in protected
regions.
"""

import re
from dataclasses import dataclass, field

import pyromark

from ._core import CJK_CLASS, squash

__all__ = ["format_text"]

_O = pyromark.Options
_OPTIONS = (
    _O.ENABLE_MATH
    | _O.ENABLE_TABLES
    | _O.ENABLE_STRIKETHROUGH
    | _O.ENABLE_TASKLISTS
    | _O.ENABLE_YAML_STYLE_METADATA_BLOCKS
    | _O.ENABLE_PLUSES_DELIMITED_METADATA_BLOCKS
)

_CJK = f"[{CJK_CLASS}]"
# Spaces between a CJK character and the end / start of a run's text.
_TRAIL_CJK = re.compile(f"{_CJK}( +)\\Z")
_LEAD_CJK = re.compile(f"\\A( +){_CJK}")

# Bare URLs, `www.` hosts, and email addresses, which pulldown-cmark leaves in
# Text.
_BARE_LINK = re.compile(
    rb"(?:https?://|www\.)[^\s<]+|(?:(?:mailto|xmpp):)?[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
    re.IGNORECASE,
)
_DOUBLE_DOLLAR = re.compile(rb"\$\$")

_SPACE = 0x20
_BACKSLASH = 0x5C
_ASTERISK = 0x2A

# Leaf events a space at a run's edge folds across.
_FOLD_LEAVES = frozenset({"Code", "InlineMath", "DisplayMath"})
# Containers a space at a run's edge folds across. Emphasis and strong
# emphasis fold only when their delimiter is `*`.
_FOLD_CONTAINERS = frozenset({"Link", "Image", "Strikethrough"})
_EMPHASIS = frozenset({"Emphasis", "Strong"})
_LINKS = frozenset({"Link", "Image"})
# Reference-link types whose label text is not edited; the label is the key
# that matches the link definition.
_LABEL_IS_KEY = frozenset({"Shortcut", "Collapsed"})


@dataclass(frozen=True)
class _Event:
    kind: str
    value: object
    start: int
    end: int

    @property
    def tag(self) -> str | None:
        """Container name of a Start/End event (`Paragraph`, `Link`, ...)."""
        if self.kind not in ("Start", "End"):
            return None
        return self.value if isinstance(self.value, str) else next(iter(self.value))

    @property
    def attrs(self):
        return None if isinstance(self.value, str) else next(iter(self.value.values()))


@dataclass
class _Run:
    """Contiguous prose made of Text fragments, with each character's source bytes.

    `spans[i]` is `(start, end)` when character i is spelled literally in the
    source, and None when it came from an entity reference. `_deletions` skips
    characters whose span is None.
    """

    first: int  # index of the first Text event
    last: int  # index of the last Text event
    start: int
    end: int
    chars: list[str] = field(default_factory=list)
    spans: list[tuple[int, int] | None] = field(default_factory=list)


def _parse(text: str) -> list[_Event]:
    events = []
    for event, span in pyromark.events_with_range(text, options=_OPTIONS):
        if isinstance(event, str):
            kind, value = event, None
        else:
            ((kind, value),) = event.items()
        events.append(_Event(kind, value, span["start"], span["end"]))
    return events


def _shape(events: list[_Event]) -> list:
    """The event stream with prose reduced to a marker.

    Every non-Text event is kept with its full value (link destinations, code
    and math content, heading levels, table alignment); each stretch of
    consecutive Text events becomes one `"Text"` marker.
    """
    shape = []
    for ev in events:
        if ev.kind == "Text":
            if not shape or shape[-1] != "Text":
                shape.append("Text")
        else:
            shape.append((ev.kind, ev.value))
    return shape


def _escaped(src: bytes, pos: int) -> bool:
    n = 0
    while pos - n > 0 and src[pos - n - 1] == _BACKSLASH:
        n += 1
    return n % 2 == 1


def _protected(src: bytes, events: list[_Event]) -> bytearray:
    """Mark the bytes no edit may touch.

    - A top-level block with a `$` byte, not escaped by a backslash, inside
      the source range of one of its Text events (outside code and front
      matter).
    - From an unescaped `$$` outside math, fenced code, code spans, and front
      matter to the next such `$$`, pairing them in order; an unpaired last one
      protects to the end.
    - A bare URL or email that starts in Text outside links and images,
      extended over the spaces on both sides.
    """
    mask = bytearray(len(src) + 1)

    def protect(start: int, end: int) -> None:
        mask[start:end] = b"\x01" * (end - start)

    opaque = []  # spans whose `$$` are not counted
    linkable = []  # Text ranges outside links, where bare links are matched
    stack: list[_Event] = []
    for ev in events:
        if ev.kind == "Start":
            stack.append(ev)
            if ev.tag == "MetadataBlock" or (
                ev.tag == "CodeBlock" and isinstance(ev.attrs, dict)
            ):
                opaque.append((ev.start, ev.end))  # front matter, fenced code
        elif ev.kind == "End":
            stack.pop()
        elif ev.kind in ("Code", "InlineMath", "DisplayMath"):
            opaque.append((ev.start, ev.end))
        elif ev.kind == "Text" and stack:
            if any(s.tag in ("CodeBlock", "MetadataBlock") for s in stack):
                continue
            if not any(s.tag in _LINKS for s in stack):
                linkable.append((ev.start, ev.end))
            for pos in range(ev.start, ev.end):
                if src[pos] == ord("$") and not _escaped(src, pos):
                    protect(stack[0].start, stack[0].end)
                    break

    tokens = [
        m.start()
        for m in _DOUBLE_DOLLAR.finditer(src)
        if not _escaped(src, m.start())
        and not any(s <= m.start() < e for s, e in opaque)
    ]
    for i in range(0, len(tokens), 2):
        end = tokens[i + 1] + 2 if i + 1 < len(tokens) else len(src)
        protect(tokens[i], end)

    for m in _BARE_LINK.finditer(src):
        start, end = m.span()
        if not any(s <= start < e for s, e in linkable):
            continue
        while start > 0 and src[start - 1] == _SPACE:
            start -= 1
        while end < len(src) and src[end] == _SPACE:
            end += 1
        protect(start, end)
    return mask


def _hides_text(start: _Event) -> bool:
    """Whether Text inside this container must not be edited."""
    if start.tag in ("CodeBlock", "MetadataBlock"):
        return True
    return start.tag in _LINKS and start.attrs["link_type"] in _LABEL_IS_KEY


def _runs(src: bytes, events: list[_Event]) -> list[_Run]:
    """Join Text fragments into runs of prose.

    Text events join when their ranges touch or are separated by a single
    backslash byte (an escape). Text inside code, front
    matter, and shortcut / collapsed reference-link and image labels is
    skipped.
    """
    runs: list[_Run] = []
    stack: list[int] = []
    excluded = 0  # open containers whose Text must not be edited
    previous_end = 0
    for i, ev in enumerate(events):
        if ev.kind == "Start":
            stack.append(i)
            excluded += _hides_text(ev)
            continue
        if ev.kind == "End":
            excluded -= _hides_text(events[stack.pop()])
            continue
        if ev.kind != "Text" or excluded:
            continue
        if ev.start < previous_end:
            raise RuntimeError(f"overlapping Text ranges at byte {ev.start}")
        previous_end = ev.end

        run = runs[-1] if runs else None
        joins = run is not None and (
            run.end == ev.start
            or (ev.start - run.end == 1 and src[run.end] == _BACKSLASH)
        )
        if not joins:
            run = _Run(first=i, last=i, start=ev.start, end=ev.end)
            runs.append(run)
        run.last, run.end = i, ev.end

        literal = src[ev.start : ev.end]
        if literal == ev.value.encode():
            pos = ev.start
            for ch in ev.value:
                width = len(ch.encode())
                run.chars.append(ch)
                run.spans.append((pos, pos + width))
                pos += width
        else:  # an entity reference
            run.chars.extend(ev.value)
            run.spans.extend([None] * len(ev.value))
    return runs


def _folds_after(src: bytes, events: list[_Event], run: _Run) -> bool:
    """Whether a space at the run's end folds into the construct that follows."""
    if run.last + 1 >= len(events):
        return False
    ev = events[run.last + 1]
    if ev.start != run.end:
        return False
    if ev.kind in _FOLD_LEAVES:
        return True
    if ev.kind != "Start":
        return False
    return ev.tag in _FOLD_CONTAINERS or (
        ev.tag in _EMPHASIS and src[ev.start] == _ASTERISK
    )


def _folds_before(src: bytes, events: list[_Event], run: _Run) -> bool:
    """Whether a space at the run's start folds into the construct before it."""
    if run.first == 0:
        return False
    ev = events[run.first - 1]
    if ev.kind in _FOLD_LEAVES:
        return ev.end == run.start
    if ev.kind != "End":
        return False
    # A collapsed reference `[x][]` is adjacent across the `[]` after its range.
    opened = _start_of(events, run.first - 1)
    gap = run.start - ev.end
    if gap == 2 and src[ev.end : run.start] == b"[]":
        adjacent = opened.tag in _LINKS and opened.attrs["link_type"] == "Collapsed"
    else:
        adjacent = gap == 0
    if not adjacent:
        return False
    return ev.tag in _FOLD_CONTAINERS or (
        ev.tag in _EMPHASIS and src[ev.end - 1] == _ASTERISK
    )


def _start_of(events: list[_Event], end_index: int) -> _Event:
    depth = 0
    for i in range(end_index, -1, -1):
        kind = events[i].kind
        if kind == "End":
            depth += 1
        elif kind == "Start":
            depth -= 1
            if depth == 0:
                return events[i]
    raise RuntimeError(f"unbalanced End event at index {end_index}")


def _deletions(src: bytes, events: list[_Event], run: _Run) -> set[int]:
    """Byte positions of the spaces this run gives up."""
    text = "".join(run.chars)
    squashed = squash(text)
    doomed = set()
    j = 0
    for i, ch in enumerate(text):
        if j < len(squashed) and squashed[j] == ch:
            j += 1
        else:
            doomed.add(i)
    if _folds_after(src, events, run) and (m := _TRAIL_CJK.search(text)):
        doomed.update(range(*m.span(1)))
    if _folds_before(src, events, run) and (m := _LEAD_CJK.match(text)):
        doomed.update(range(*m.span(1)))

    positions = set()
    for i in doomed:
        span = run.spans[i]
        if span is None:  # spelled as an entity reference, not a literal space
            continue
        if src[span[0] : span[1]] != b" ":
            raise RuntimeError(f"deletion candidate at byte {span[0]} is not a space")
        positions.add(span[0])
    return positions


def _groups(positions: set[int]) -> list[frozenset[int]]:
    """Split byte positions into maximal runs of consecutive bytes."""
    groups: list[list[int]] = []
    for pos in sorted(positions):
        if groups and groups[-1][-1] == pos - 1:
            groups[-1].append(pos)
        else:
            groups.append([pos])
    return [frozenset(g) for g in groups]


def _delete(src: bytes, positions: set[int]) -> bytes:
    return bytes(b for i, b in enumerate(src) if i not in positions)


def _only_spaces_removed(before: bytes, after: bytes) -> bool:
    """Whether `after` is `before` with some U+0020 bytes deleted."""
    j = 0
    for b in before:
        if j < len(after) and after[j] == b:
            j += 1
        elif b != _SPACE:
            return False
    return j == len(after)


def _pass(text: str) -> str:
    src = text.encode()
    events = _parse(text)
    mask = _protected(src, events)

    positions = set()
    for run in _runs(src, events):
        positions |= _deletions(src, events, run)
    groups = [g for g in _groups(positions) if not any(mask[p] for p in g)]
    if not groups:
        return text

    # Keep the deletions only if the result has the same `_shape`; otherwise
    # add groups one at a time, keeping each that preserves it. In
    # `日本 **(a)** 語` both spaces stay: deleting either one turns the `**`
    # into literal text.
    shape = _shape(events)
    accepted = set().union(*groups)
    if _shape(_parse(_delete(src, accepted).decode())) != shape:
        accepted = set()
        for group in groups:
            trial = accepted | group
            if _shape(_parse(_delete(src, trial).decode())) == shape:
                accepted = trial

    out = _delete(src, accepted)
    if not _only_spaces_removed(src, out):
        raise RuntimeError("an edit removed something other than a space")
    return out.decode()


def format_text(text: str) -> str:
    """Remove spaces adjacent to CJK characters in Markdown `text`.

    The result is `text` with some U+0020 characters deleted, and pulldown-cmark
    parses it to the same `_shape`. Passes repeat until one changes nothing, so
    `format_text` of the result returns it unchanged.
    """
    while True:
        out = _pass(text)
        if out == text:
            return out
        text = out
