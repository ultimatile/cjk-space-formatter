"""Resolve the cjk-latin-space core under one import path for dev and wheel.

The dev workspace installs `cjk_latin_space` editable, so it is preferred there
and always reflects live core edits. In a published wheel that package is absent
(core is never published to an index), so the import falls back to the build-time
vendored `_cjk_latin_space` beside this file. Each published package vendors
under its own private name, so two installed packages never collide.

Dev-first ordering is deliberate. The editable install's build hook also writes
`_cjk_latin_space.py` into the working tree, so a vendored-first order would let
that copy shadow live core edits during development (the bug this avoids). The
only cost is that a published wheel would prefer an externally-installed
top-level `cjk_latin_space` over its vendored copy — but since core is never
published, no such package can exist on a user's system, so the wheel stays
self-contained in practice.
"""

try:
    from cjk_latin_space import CJK_CLASS, squash  # dev workspace: live core
except ImportError:  # published wheel: build-time vendored copy
    from ._cjk_latin_space import CJK_CLASS, squash

__all__ = ["CJK_CLASS", "squash"]
