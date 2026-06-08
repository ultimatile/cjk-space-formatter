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

```sh
pip install typst-cjk-latin-space-remover
typst-cjk-latin-space-remover -i your.typ     # edit in place
cat your.typ | typst-cjk-latin-space-remover  # stdin -> stdout
```

`--check` exits non-zero if a file would change; `--diff` shows a unified diff.

## Non-goals

The half-width colon is preserved (`注: これは`). Pathological raw blocks (rare
nesting, multi-backtick inline raw, info strings) are out of scope; the common
fence and span forms are the contract.
