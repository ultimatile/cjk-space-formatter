"""Resolve the cjk-latin-space core outside a published wheel.

A published wheel never contains this file: the wheel target excludes it, and
`hatch_build.py` force-includes a shim that reaches the build-time vendored copy
through a relative import. That substitution is gated on the standard build, so
this file is what an editable install and a plain source checkout use.

The workspace installs `cjk_latin_space` as an editable member, so the first
import reflects live edits to `core/`. That ordering is deliberate: uv refreshes
the vendored copy only on a forced reinstall, so preferring it here would serve a
stale core for the rest of a development session. The fallback covers an install
with no workspace core to reach — `cjk-latin-space` is deliberately not a runtime
dependency — where the vendored copy is the only core available. Without it this
module would raise on import, and since the package registers an mdformat parser
extension, that would break every mdformat run in the environment.
"""

try:
    from cjk_latin_space import CJK_CLASS, squash  # workspace: live core
except ImportError:  # no workspace core: build-time vendored copy
    from ._cjk_latin_space import CJK_CLASS, squash

__all__ = ["CJK_CLASS", "squash"]
