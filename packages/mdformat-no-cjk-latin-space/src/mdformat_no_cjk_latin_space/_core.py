"""Resolve the cjk-latin-space core under one import path for dev and wheel.

The dev workspace installs `cjk_latin_space` editable, so it is preferred there
and always reflects live core edits (no stale vendored copy can mask them). In a
published wheel that package is absent (core is never published), so the import
falls back to `_cjk_latin_space`, which the build hook vendors beside this file.
The two published packages vendor under their own private name, so there is no
top-level name collision when both are installed.
"""

try:
    from cjk_latin_space import CJK_CLASS, squash  # dev workspace: live core
except ImportError:  # published wheel: build-time vendored copy
    from ._cjk_latin_space import CJK_CLASS, squash

__all__ = ["squash", "CJK_CLASS"]
