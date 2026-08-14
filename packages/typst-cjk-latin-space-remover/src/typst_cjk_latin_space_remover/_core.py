"""Resolve the cjk-latin-space core for the development workspace.

The workspace installs `cjk_latin_space` as an editable member, so this import
always reflects live edits to `core/`. A published wheel never contains this
file: the wheel target excludes it, and `hatch_build.py` force-includes a shim
that reaches the build-time vendored copy through a relative import instead.

The two contexts need opposite things, which is why the file differs between
them. Development must not read the vendored copy, because uv refreshes that
copy only on a forced reinstall and it therefore goes stale across ordinary
edits to `core/`. A wheel must not read the top-level module, because any
installed distribution can provide that name. A relative import resolves only
within the package's own `__path__` and never consults `sys.path`, so the
wheel's shim cannot be shadowed.
"""

from cjk_latin_space import CJK_CLASS, squash

__all__ = ["CJK_CLASS", "squash"]
