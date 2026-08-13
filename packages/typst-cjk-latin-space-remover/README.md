# typst-cjk-latin-space-remover

A CLI that removes unwanted spaces between CJK characters and adjacent Latin
letters or digits in [Typst](https://typst.app/) files — the inverse of CSS
`text-autospace: ideograph-alpha`, which *inserts* such spacing.

```
日本語 English テスト        ->  日本語Englishテスト
行列 $x$ の計算               ->  行列$x$の計算
式 @eq:fidelity の計算       ->  式@eq:fidelity の計算   (space terminating @label kept)
```

## Protected spans

Edits are made surgically — only the targeted CJK-adjacent spaces change. These
Typst spans are protected:

- inline / block math: `$...$`, and `$ ... $` blocks
- inline / block raw: `` `code` `` and ```` ```lang ... ``` ```` fences
- hash expressions: `#set heading(...)`, `#sym.ballot`, … (terminating space kept)
- label references: `@eq:fidelity` (terminating space kept)
- structural prefixes: `=` headings, `-`/`+` bullets, `1.` ordered markers

## Install & use

**Provisional and unreleased** — the Non-goals below are what gates a release.
Install from this repository:

```sh
pip install "git+https://github.com/ultimatile/cjk-space-formatter#subdirectory=packages/typst-cjk-latin-space-remover"
typst-cjk-latin-space-remover -i your.typ     # edit in place
cat your.typ | typst-cjk-latin-space-remover  # stdin -> stdout
```

`--check` exits non-zero if a file would change; `--diff` shows a unified diff.

## Non-goals

The half-width colon is preserved (`注: これは`). Pathological raw blocks (rare
nesting, multi-backtick inline raw, info strings) are out of scope; the common
fence and span forms are the contract.

Block math and block raw are detected line by line, not by a full Typst parser,
so constructs that break the line heuristic are out of scope. A block-math close
`$` must sit on its own line: a `$` that closes at the end of a content line
(`$ a +` … `  b $`) is not detected, so the following lines stay unformatted
(the math itself is left intact — the failure under-formats, it never corrupts).
A line comment trailing a close line (`$ <label> // note`), or a fence-like line
(```` ``` ````) inside a `/* … */` block comment, can likewise leave the detector
in the wrong state. Keep such constructs out of the files you format.

The hash-expression scanner protects an expression's head and its terminating
space, not arbitrary code-mode bodies. A space *inside* a `#let` / `#show` value
— a string or content block such as `#let x = "日本 語"` — is not protected and
may be collapsed. Protecting it correctly would require a real Typst parser,
which this tool does not currently use. Keep CJK-adjacent spaces out of
code-mode string/content literals, or guard those lines.
