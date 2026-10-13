# typst-cjk-latin-space-remover

A CLI that removes the spaces next to CJK characters in
[Typst](https://typst.app/) files: a run of spaces between two non-space
characters goes when either side is CJK, except a space right after a
half-width colon. This is the inverse of CSS `text-autospace: ideograph-alpha`,
which *inserts* spacing between CJK and Latin text.

```
日本語 English テスト     ->  日本語Englishテスト
行列 $x$ の計算            ->  行列$x$の計算
式 @eq:fidelity の計算    ->  式@eq:fidelity の計算
```

## Only the spaces change

The output is the input with some spaces deleted. Every other byte is
unchanged, including line endings. A deletion is kept only if Typst parses the
result to the same structure: in the last example above, the space after
`@eq:fidelity` stays, because without it the reference would name the label
`eq:fidelityの計算`.

Only markup prose is edited. Math, raw text, comments, and code — including
string literals such as `#let x = "日本 語"` — keep their spaces. A content
block inside code is markup, so `#text(red)[日本 語]` is edited.

A space before an ASCII quote (`'` or `"`) stays.

## Which Typst it reads

Files are read with the [`typst-syntax`](https://crates.io/crates/typst-syntax)
parser. A file with a syntax error is left unchanged: the CLI prints the errors
with their line numbers and exits with status 2.

## Install & use

Install from this repository with [Cargo](https://doc.rust-lang.org/cargo/):

```sh
cargo install --locked --git https://github.com/ultimatile/cjk-space-formatter typst-cjk-latin-space-remover
```

```sh
typst-cjk-latin-space-remover -i your.typ     # edit in place
cat your.typ | typst-cjk-latin-space-remover  # stdin -> stdout
```

`--check` exits with status 1 if a file would change; `--diff` shows a unified
diff. Without a flag, each file is printed, changed or not.

As a [pre-commit](https://pre-commit.com/) hook, which edits the staged `.typ`
files in place:

```yaml
- repo: https://github.com/ultimatile/cjk-space-formatter
  rev: <commit>
  hooks:
    - id: typst-cjk-latin-space-remover
```

## Non-goals

- The half-width colon is preserved (`注: これは`).
- Text is not reflowed and no space is ever inserted.
