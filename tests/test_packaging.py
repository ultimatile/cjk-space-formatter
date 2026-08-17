"""Packaging invariants for the two published wheels.

A wheel must reach the shared core through a relative import. That is the whole
protection: a relative import resolves within the package's own ``__path__`` and
never consults ``sys.path``, so no installed distribution providing a top-level
``cjk_latin_space`` can take over. The development tree needs the opposite --
the live workspace core -- so the two differ, and these tests pin each side.
"""

from __future__ import annotations

import subprocess
import sys
import sysconfig
import tarfile
import tempfile
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


def _run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, and on failure report what the child said.

    `check=True` alone raises with the exit status only, which for a build
    backend discards the one thing a reader needs -- the hook's own error and
    the backend's traceback.
    """
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False, **kwargs
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"{' '.join(command)}\nexited {completed.returncode}\n"
            f"--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}"
        )
    return completed


def _build(dist: str, flag: str, out_dir: Path, suffix: str) -> Path:
    """Build one artifact into out_dir and return its path there."""
    _run(["uv", "build", "--package", dist, flag, "-o", str(out_dir)], cwd=REPO_ROOT)
    produced = sorted(out_dir.glob(f"*{suffix}"))
    assert len(produced) == 1, produced
    return produced[0]


@pytest.fixture(scope="session")
def artifacts(tmp_path_factory):
    """Build both packages' wheel and sdist once for the whole session.

    The artifacts land outside the source tree, so a run killed mid-build leaves
    nothing behind for a later build to pick up.
    """
    built: dict[str, dict[str, Path]] = {}
    for dist, module in PACKAGES:
        out_dir = tmp_path_factory.mktemp(module)
        built[module] = {
            "wheel": _build(dist, "--wheel", out_dir, ".whl"),
            "sdist": _build(dist, "--sdist", out_dir, ".tar.gz"),
        }
    return built


def _run_probe(source: str) -> str:
    return _run([sys.executable, "-c", source]).stdout.strip()


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
    # The tracked file, not the shim: it still prefers the workspace core, and
    # its marker docstring line is absent.
    assert "from cjk_latin_space import CJK_CLASS, squash" in body
    assert "Generated by hatch_build.py" not in body


@pytest.mark.parametrize(("dist", "module"), PACKAGES, ids=PACKAGE_IDS)
def test_editable_install_outside_the_workspace(tmp_path, dist, module):
    """An editable install with no workspace core must still work.

    Two things are pinned here. The shim is gated on the standard build, so a
    PEP 660 install must not receive it: such an install redirects to the source
    tree, where the tracked _core.py is what must stay in effect, and a file
    appearing under site-packages is the signal that a standard-build artifact
    slipped through the gate. And the tracked _core.py must fall back to the
    vendored copy, because `cjk-latin-space` is deliberately not a runtime
    dependency and so is absent here -- an import error would take the package's
    entry points down with it.
    """
    venv = tmp_path / "venv"
    # Pinned to this interpreter so that the version-keyed site-packages path
    # computed below is right by construction rather than by coincidence.
    _run(["uv", "venv", "--python", sys.executable, str(venv)])
    # `--python` takes the environment's root directory, so no interpreter path
    # is spelled out here.
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(venv),
            "-e",
            str(REPO_ROOT / "packages" / dist),
        ]
    )
    # The `venv` scheme resolves to posix_venv or nt_venv per platform.
    site_packages = Path(
        sysconfig.get_path(
            "purelib",
            scheme="venv",
            vars={
                "base": str(venv),
                "py_version_short": f"{sys.version_info.major}.{sys.version_info.minor}",
            },
        )
    )

    # Without this the next assertion would also hold for an install that never
    # happened. A non-editable install would land the shim here and fail it.
    assert list(site_packages.glob(f"{module}-*.dist-info")), "install did not run"
    assert not (site_packages / module / "_core.py").exists()

    resolved = _run(
        [
            "uv",
            "run",
            "--python",
            str(venv),
            "--no-project",
            "python",
            "-c",
            f"import {module} as m; print(m.squash.__module__)",
        ]
    ).stdout.strip()
    assert resolved == f"{module}._cjk_latin_space"


def test_a_wheel_build_leaves_no_shim_directory(tmp_path):
    """The shim's scratch directory does not outlive the build that made it.

    Cleanup rides on the TemporaryDirectory's finalizer in the build backend's
    own process, so it is observable only from outside that process, as whatever
    the build did or did not leave in the system temporary directory.
    """
    system_tmp = Path(tempfile.gettempdir())
    before = set(system_tmp.glob("core-shim-*"))

    _build(PACKAGES[0][0], "--wheel", tmp_path, ".whl")

    assert not set(system_tmp.glob("core-shim-*")) - before


@pytest.mark.parametrize(("dist", "module"), PACKAGES, ids=PACKAGE_IDS)
def test_development_import_resolves_to_the_workspace_core(dist, module):
    """The editable install must not read the build-time vendored copy.

    uv refreshes that copy only on a forced reinstall, so reading it here would
    serve a stale core for the rest of a development session.
    """
    probe = f"from {module}._core import squash\nprint(squash.__module__)\n"
    assert _run_probe(probe) == "cjk_latin_space"
