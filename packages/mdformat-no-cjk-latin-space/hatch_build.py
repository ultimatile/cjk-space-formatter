"""Build-time vendor of the shared cjk-latin-space core into this package.

Copies core/src/cjk_latin_space/__init__.py to src/<pkg>/_cjk_latin_space.py so
the built sdist and wheel are self-contained: core is never a runtime dependency
and there is no path/workspace reference to resolve at install time. The copy is
made for both the sdist and wheel targets, so building a wheel from an already
built sdist works even though the core source lives outside the sdist — by then
the vendored copy is already inside it, and a missing source is tolerated.
"""

import shutil
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_VENDOR_DEST = "src/mdformat_no_cjk_latin_space/_cjk_latin_space.py"


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        root = Path(self.root)
        source = (
            root / ".." / ".." / "core" / "src" / "cjk_latin_space" / "__init__.py"
        ).resolve()
        dest = root / _VENDOR_DEST
        if source.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        elif not dest.is_file():
            raise FileNotFoundError(
                f"core source {source} not found and no vendored copy at {dest}"
            )
