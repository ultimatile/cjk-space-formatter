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

_BOM = "﻿"
_MAX_REJECTIONS = 32

_SPACE = 0x20
_BACKSLASH = 0x5C
_ASTERISK = 0x2A

# Leaf events whose content is never edited; a space at a run's edge folds
# across them.
_OPAQUE_LEAVES = frozenset({"Code", "InlineMath", "DisplayMath"})
# Containers whose Text is never edited.
_RAW_BLOCKS = frozenset({"CodeBlock", "MetadataBlock"})
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
    """The event stream with the spaces taken out of its prose.

    Every non-Text event is kept with its full value (link destinations, code
    and math content, heading levels, table alignment); each stretch of
    consecutive Text events becomes one `("Text", content)` entry, with U+0020
    removed from the content.
    """
    shape = []
    for ev in events:
        if ev.kind == "Text":
            content = ev.value.replace(" ", "")
            if shape and shape[-1][0] == "Text":
                shape[-1] = ("Text", shape[-1][1] + content)
            else:
                shape.append(("Text", content))
        else:
            shape.append((ev.kind, ev.value))
    return shape


def _escaped(src: bytes, pos: int) -> bool:
    n = 0
    while pos - n > 0 and src[pos - n - 1] == _BACKSLASH:
        n += 1
    return n % 2 == 1


def _prose(events: list[_Event]):
    """Yield each Text event outside code and front matter, with the open containers."""
    stack: list[_Event] = []
    for ev in events:
        if ev.kind == "Start":
            stack.append(ev)
        elif ev.kind == "End":
            stack.pop()
        elif ev.kind == "Text" and not any(s.tag in _RAW_BLOCKS for s in stack):
            yield ev, stack


def _unparsed_dollar(src: bytes, events: list[_Event]) -> bool:
    """Whether a `$` byte, not escaped by a backslash, lies in the source range
    of a Text event outside code and front matter."""
    for ev, _ in _prose(events):
        pos = src.find(b"$", ev.start, ev.end)
        while pos != -1:
            if not _escaped(src, pos):
                return True
            pos = src.find(b"$", pos + 1, ev.end)
    return False


def _protected(src: bytes, events: list[_Event]) -> bytearray:
    """Mark the bytes no edit may touch.

    These are the bare URLs and emails that start in Text outside links and
    images, extended over the spaces on both sides.
    """
    mask = bytearray(len(src) + 1)
    for ev, stack in _prose(events):
        if any(s.tag in _LINKS for s in stack):
            continue
        for m in _BARE_LINK.finditer(src, ev.start, ev.end):
            _protect_bare_link(src, mask, m.start())
    return mask


def _protect_bare_link(src: bytes, mask: bytearray, start: int) -> None:
    """Protect the bare link that starts at `start`, and the spaces around it.

    The match runs to its full length, past the end of the Text range it
    starts in.
    """
    end = _BARE_LINK.match(src, start).end()
    while start > 0 and src[start - 1] == _SPACE:
        start -= 1
    while end < len(src) and src[end] == _SPACE:
        end += 1
    mask[start:end] = b"\x01" * (end - start)


def _hides_text(start: _Event) -> bool:
    """Whether Text inside this container must not be edited."""
    if start.tag in _RAW_BLOCKS:
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
    """Whether a space at the run's end folds into the next event."""
    if run.last + 1 >= len(events):
        return False
    ev = events[run.last + 1]
    if ev.kind in _OPAQUE_LEAVES:
        return True
    if ev.kind != "Start":
        return False
    return ev.tag in _FOLD_CONTAINERS or (
        ev.tag in _EMPHASIS and src[ev.start] == _ASTERISK
    )


def _folds_before(src: bytes, events: list[_Event], run: _Run) -> bool:
    """Whether a space at the run's start folds into the previous event."""
    if run.first == 0:
        return False
    ev = events[run.first - 1]
    if ev.kind in _OPAQUE_LEAVES:
        return True
    if ev.kind != "End":
        return False
    return ev.tag in _FOLD_CONTAINERS or (
        ev.tag in _EMPHASIS and src[ev.end - 1] == _ASTERISK
    )


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
    out = bytearray()
    kept_from = 0
    for pos in sorted(positions):
        out += src[kept_from:pos]
        kept_from = pos + 1
    out += src[kept_from:]
    return bytes(out)


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
    if _unparsed_dollar(src, events):
        return text
    mask = _protected(src, events)

    positions = set()
    for run in _runs(src, events):
        positions |= _deletions(src, events, run)
    groups = [g for g in _groups(positions) if not any(mask[p] for p in g)]
    if not groups:
        return text

    # Keep deletions only if the result has the same `_shape`. A set of groups
    # that changes it is halved until each half keeps the shape or is a single
    # group, which is then dropped. In `日本 **(a)** 語` both spaces stay:
    # deleting either one turns the `**` into literal text. After
    # `_MAX_REJECTIONS` dropped groups, the groups not yet tried are dropped
    # too.
    shape = _shape(events)
    accepted: set[int] = set()
    rejections = 0

    def accept(batch: list[frozenset[int]]) -> None:
        nonlocal accepted, rejections
        if rejections >= _MAX_REJECTIONS:
            return
        trial = accepted.union(*batch)
        if _shape(_parse(_delete(src, trial).decode())) == shape:
            accepted = trial
        elif len(batch) > 1:
            accept(batch[: len(batch) // 2])
            accept(batch[len(batch) // 2 :])
        else:
            rejections += 1

    accept(groups)
    out = _delete(src, accepted)
    if not _only_spaces_removed(src, out):
        raise RuntimeError("an edit removed something other than a space")
    return out.decode()


def format_text(text: str) -> str:
    """Remove spaces adjacent to CJK characters in Markdown `text`.

    The result is `text` with some U+0020 characters deleted, and pulldown-cmark
    parses it to the same `_shape`. A `text` whose prose holds a `$` not
    escaped by a backslash (see `_unparsed_dollar`) is returned unchanged. A
    leading BOM is set aside
    while parsing, so front matter after it is recognised. Passes repeat until
    one changes nothing, so `format_text` of the result returns it unchanged.
    """
    bom = _BOM if text.startswith(_BOM) else ""
    text = text.removeprefix(bom)
    while True:
        out = _pass(text)
        if out == text:
            return bom + out
        text = out
