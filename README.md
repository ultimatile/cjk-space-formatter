# cjk-latin-space

Tools that **remove** unwanted spaces between CJK characters and adjacent
Latin letters, digits, or math — the spaces LLMs tend to insert when they carry
English spacing conventions into Japanese text. This is the inverse of CSS
`text-autospace: ideograph-alpha` and of pangu-style tools, which *add* such
spacing.

```
任意の2量子ビットユニタリゲート $U in S U(4)$ を分解する
->  任意の2量子ビットユニタリゲート$U in S U(4)$を分解する
```

## Scope

These tools are intended for CJK prose containing occasional Latin text, math,
or code. Do not use them for primarily Latin prose: spaces around CJK text may
be meaningful.

## Packages

This repository ships separate packages for Markdown and Typst:

| You edit…    | Use                                                                             | Form            | Status      |
| ------------ | ------------------------------------------------------------------------------- | --------------- | ----------- |
| **Markdown** | [`markdown-cjk-latin-space-remover`](packages/markdown-cjk-latin-space-remover) | standalone CLI  | usable      |
| **Markdown** | [`mdformat-no-cjk-latin-space`](packages/mdformat-no-cjk-latin-space)           | mdformat plugin | usable      |
| **Typst**    | [`typst-cjk-latin-space-remover`](packages/typst-cjk-latin-space-remover)       | standalone CLI  | provisional |

For Markdown, the CLI deletes spaces and leaves every other byte unchanged. The
plugin runs inside mdformat, which re-formats the whole document; it is for
repositories that already format their Markdown with mdformat.

Each package's README has install and usage instructions. None is on PyPI; all
install from this repository.

The Typst tool is **provisional**. Its scanner has known limitations documented
in the package README, and the package remains unreleased.

## Migrating from `cjk-space-formatter`

The single `cjk-space-formatter` CLI that handled both formats is **deprecated**
in favour of the tools above. For Markdown, `markdown-cjk-latin-space-remover`
takes the same `-i` / `--check` / `--diff` flags as `cjk-space-formatter`;
without a flag it prints every file, including unchanged ones. For Typst,
`typst-cjk-latin-space-remover file.typ` replaces `cjk-space-formatter file.typ`,
subject to the provisional status above.

## Repository layout

```
packages/
  markdown-cjk-latin-space-remover/  # published from here; not on PyPI yet
  mdformat-no-cjk-latin-space/       # published from here; not on PyPI yet
  typst-cjk-latin-space-remover/     # provisional, unreleased
core/                                # cjk-latin-space core: squash(plain_run) — build-time vendored, not published
conformance/                         # pure-run core corpus, target-independent
```

The shared core holds only the format-independent invariant — collapsing
CJK<->Latin/digit spaces within a plain run (with the half-width colon as the
sole exception). Span/boundary protection is each tool's own plumbing. The core
is vendored into each wheel at build time, so it is never a runtime dependency
and the packages release independently.

## Alternatives

Several tools touch CJK / half-width spacing; they differ by **direction** (add
vs remove) and **target**:

| Tool                                                                                                                          | Direction                                  | Target                             |
| ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ---------------------------------- |
| [pangu](https://github.com/vinta/pangu.js)                                                                                    | adds spaces                                | HTML / plain text (not for markup) |
| [Prettier](https://github.com/prettier/prettier/issues/6385)                                                                  | adds in Markdown by default (configurable) | code / Markdown                    |
| [textlint](https://github.com/textlint/textlint) + [textlint-plugin-typst](https://github.com/textlint/textlint-plugin-typst) | removes (`--fix`able)                      | Markdown / Typst / text            |
| **this repo**                                                                                                                 | removes                                    | Markdown / Typst source            |

Off-the-shelf textlint rules cannot protect `$...$`: a plain Markdown AST has no
math concept. These tools solve that by owning the math/span model — the Markdown
CLI via pulldown-cmark's math extension, the Markdown plugin via dollarmath, the
Typst CLI via its own scanner.

## Development

```bash
uv sync                       # installs every package + core (editable) and pytest
uv run pytest
```

The core is resolved from the editable workspace install during development, so
edits to `core/` take effect immediately without rebuilding the vendored copy.
