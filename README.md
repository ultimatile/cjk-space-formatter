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

## Which tool do you want?

The spaces are easy; the hard part is **not touching** math, code, and other
spans where a space is meaningful. Markdown and Typst protect different spans in
different ways, so this repo ships **two** tools rather than one tool that half-
serves both:

| You edit…    | Use                                                                          | Form             |
| ------------ | ---------------------------------------------------------------------------- | ---------------- |
| **Markdown** | [`mdformat-no-cjk-latin-space`](packages/mdformat-no-cjk-latin-space)        | mdformat plugin  |
| **Typst**    | [`typst-cjk-latin-space-remover`](packages/typst-cjk-latin-space-remover)    | standalone CLI   |

Each package's README has install and usage. The Markdown tool builds on
mdformat + dollarmath, so fence/code/math protection is structural (the parser
never exposes their interior). The Typst tool is a self-contained CLI with a
regex/state-machine scanner for Typst's spans (`$`, `` ` ``, `#expr`, `@ref`,
list markers).

## Migrating from `cjk-space-formatter`

The single `cjk-space-formatter` CLI that handled both formats is **deprecated**
in favour of the two tools above. Replace `cjk-space-formatter file.typ` with
`typst-cjk-latin-space-remover file.typ`; for Markdown, install the plugin and
run `mdformat`.

## Repository layout

```
packages/
  mdformat-no-cjk-latin-space/    # PyPI
  typst-cjk-latin-space-remover/  # PyPI
core/                             # cjk-latin-space core: squash(plain_run) — build-time vendored, not published
conformance/                      # pure-run core corpus, target-independent
```

The shared core holds only the format-independent invariant — collapsing
CJK<->Latin/digit spaces within a plain run (with the half-width colon as the
sole exception). Span/boundary protection is each tool's own plumbing. The core
is vendored into each wheel at build time, so it is never a runtime dependency
and the two packages release independently.

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
plugin via dollarmath, the Typst CLI via its own scanner.

## Development

```bash
uv sync                       # installs both packages + core (editable) and pytest
uv run pytest conformance packages
```

The core is resolved from the editable workspace install during development, so
edits to `core/` take effect immediately without rebuilding the vendored copy.
