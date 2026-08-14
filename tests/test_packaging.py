"""Packaging invariants for the two published wheels.

A wheel must reach the shared core through a relative import. That is the whole
protection: a relative import resolves within the package's own ``__path__`` and
never consults ``sys.path``, so no installed distribution providing a top-level
``cjk_latin_space`` can take over. The development tree needs the opposite --
the live workspace core -- so the two differ, and these tests pin each side.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# (distribution name, importable module name)
PACKAGES = [
    ("mdformat-no-cjk-latin-space", "mdformat_no_cjk_latin_space"),
    ("typst-cjk-latin-space-remover", "typst_cjk_latin_space_remover"),
]
PACKAGE_IDS = [module for _, module in PACKAGES]

# A stand-in for any unrelated distribution that happens to publish the generic
# top-level module name with both of the names the core exports.
FOREIGN_CORE = 'CJK_CLASS = "FOREIGN"\n\n\ndef squash(plain_run):\n    return "FOREIGN::" + plain_run\n'


def _build(dist: str, flag: str, out_dir: Path, suffix: str) -> Path:
    """Build one artifact and return it, copied out of the working tree."""
    subprocess.run(
        ["uv", "build", "--package", dist, flag, "-o", str(out_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    produced = sorted(out_dir.glob(f"*{suffix}"))
    assert len(produced) == 1, produced
    return produced[0]


@pytest.fixture(scope="session")
def artifacts(tmp_path_factory):
    """Build both packages' wheel and sdist once for the whole session.

    The output directory sits inside the package root on purpose. That is the
    case where a forced file and an ordinarily selected file claim the same
    archive path, which hatchling rejects unless the wheel target excludes the
    tracked file -- so building anywhere else would leave that path uncovered.
    """
    built: dict[str, dict[str, Path]] = {}
    for dist, module in PACKAGES:
        out_dir = REPO_ROOT / "packages" / dist / "dist"
        shutil.rmtree(out_dir, ignore_errors=True)
        kept = tmp_path_factory.mktemp(module)
        try:
            wheel = _build(dist, "--wheel", out_dir, ".whl")
            shutil.copyfile(wheel, kept / wheel.name)
            wheel_copy = kept / wheel.name
            for stale in out_dir.glob("*.whl"):
                stale.unlink()

            sdist = _build(dist, "--sdist", out_dir, ".tar.gz")
            shutil.copyfile(sdist, kept / sdist.name)
            sdist_copy = kept / sdist.name
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)
        built[module] = {"wheel": wheel_copy, "sdist": sdist_copy}
    return built


def _run_probe(source: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _extract_wheel(wheel: Path, into: Path) -> Path:
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(into)
    return into


@pytest.mark.parametrize(("dist", "module"), PACKAGES, ids=PACKAGE_IDS)
def test_wheel_ships_exactly_one_core_and_one_vendored_copy(artifacts, dist, module):
    with zipfile.ZipFile(artifacts[module]["wheel"]) as archive:
        names = archive.namelist()
        body = archive.read(f"{module}/_core.py").decode()

    assert [n for n in names if n == f"{module}/_core.py"] == [f"{module}/_core.py"]
    # The shim's relative import is worthless if its target is not in the wheel.
    assert [n for n in names if n == f"{module}/_cjk_latin_space.py"] == [
        f"{module}/_cjk_latin_space.py"
    ]
    assert "from ._cjk_latin_space import CJK_CLASS, squash" in body
    assert "from cjk_latin_space import" not in body


@pytest.mark.parametrize(("dist", "module"), PACKAGES, ids=PACKAGE_IDS)
def test_wheel_ignores_a_foreign_top_level_core(artifacts, tmp_path, dist, module):
    package_root = _extract_wheel(artifacts[module]["wheel"], tmp_path / "wheel")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "cjk_latin_space.py").write_text(FOREIGN_CORE)

    # The foreign module precedes site-packages, so it would win any lookup that
    # reaches sys.path at all; the extracted wheel precedes it so that the
    # package under test is the built artifact rather than the working tree.
    probe = (
        "import sys\n"
        f"sys.path.insert(0, {str(foreign)!r})\n"
        f"sys.path.insert(0, {str(package_root)!r})\n"
        f"from {module}._core import squash\n"
        "print(squash('日本語 test'))\n"
    )
    assert _run_probe(probe) == "日本語test"


def test_typst_public_api_from_the_wheel_ignores_a_foreign_core(artifacts, tmp_path):
    module = "typst_cjk_latin_space_remover"
    package_root = _extract_wheel(artifacts[module]["wheel"], tmp_path / "wheel")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "cjk_latin_space.py").write_text(FOREIGN_CORE)

    probe = (
        "import sys\n"
        f"sys.path.insert(0, {str(foreign)!r})\n"
        f"sys.path.insert(0, {str(package_root)!r})\n"
        f"from {module} import format_text\n"
        "print(format_text('日本語 test 123'))\n"
    )
    assert _run_probe(probe) == "日本語test 123"


@pytest.mark.parametrize(("dist", "module"), PACKAGES, ids=PACKAGE_IDS)
def test_sdist_keeps_the_tracked_development_core(artifacts, dist, module):
    """The shim is gated to the standard wheel, so the sdist must not carry it."""
    with tarfile.open(artifacts[module]["sdist"]) as archive:
        members = [n for n in archive.getnames() if n.endswith("_core.py")]
        assert len(members) == 1, members
        extracted = archive.extractfile(members[0])
        assert extracted is not None
        body = extracted.read().decode()

    assert members[0].endswith(f"src/{module}/_core.py")
    assert "from cjk_latin_space import CJK_CLASS, squash" in body
    assert "from ._cjk_latin_space import" not in body


@pytest.mark.parametrize(("dist", "module"), PACKAGES, ids=PACKAGE_IDS)
def test_development_import_resolves_to_the_workspace_core(dist, module):
    """The editable install must not read the build-time vendored copy.

    uv refreshes that copy only on a forced reinstall, so reading it here would
    serve a stale core for the rest of a development session.
    """
    probe = f"from {module}._core import squash\nprint(squash.__module__)\n"
    assert _run_probe(probe) == "cjk_latin_space"
