"""Conformance corpus for the cjk-latin-space invariant.

`cases.json` is the contract every implementation of the invariant must
satisfy: a JSON array of `[input, expected]` pairs. Inputs are PURE RUNS — no
protected spans (no math, code, refs) — so there is no target dimension:
`squash(str) -> str` is exercised directly. This module runs the cases against
the Python core; `crates/cjk-latin-space-typst-core` runs the same file against
its Rust implementation of the rule. Front-end-specific behaviour (protected
spans, boundaries, document re-normalisation) is tested in each package's own
suite, not here.
"""

import json
from pathlib import Path

import pytest
from cjk_latin_space import squash

CASES = json.loads(Path(__file__).with_name("cases.json").read_text(encoding="utf-8"))


def test_corpus_size():
    assert len(CASES) == 21


@pytest.mark.parametrize("text, expected", CASES, ids=[c[0] or "empty" for c in CASES])
def test_squash(text, expected):
    assert squash(text) == expected
