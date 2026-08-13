"""Conformance corpus for the cjk-latin-space core.

The single machine-shared contract both front-ends must satisfy. Inputs are
PURE RUNS — no protected spans (no math, code, refs) — so there is no target
dimension: `squash(str) -> str` is exercised directly. Front-end-specific
behaviour (protected spans, boundaries, document re-normalisation) is tested in
each package's own e2e suite, not here.
"""

import pytest
from cjk_latin_space import squash

CASES = [
    # CJK <-> Latin within a run.
    ("日本語 English テスト", "日本語Englishテスト"),
    ("パラメータは Weyl chamber に", "パラメータはWeyl chamberに"),
    # CJK <-> digit within a run.
    ("最大 3 個の項目", "最大3個の項目"),
    ("1.5 個", "1.5個"),
    # CJK <-> CJK collapses too (the invariant is "CJK on at least one side").
    ("日本 語", "日本語"),
    # Multiple spaces collapse.
    ("テスト  です", "テストです"),
    # Half-width colon is the sole exception: space after it before CJK stays.
    ("注: これはテスト", "注: これはテスト"),
    ("定義: 任意の", "定義: 任意の"),
    # The exception is one-directional — it covers the space *after* the colon,
    # so a space between CJK and a following colon still collapses.
    ("見出し : 値", "見出し: 値"),
    # Pure ASCII / pure CJK are untouched.
    ("Weyl chamber theorem", "Weyl chamber theorem"),
    ("Hello World", "Hello World"),
    ("純粋な日本語テキスト", "純粋な日本語テキスト"),
    ("", ""),
]


@pytest.mark.parametrize("text, expected", CASES, ids=[c[0] or "empty" for c in CASES])
def test_squash(text, expected):
    assert squash(text) == expected
