# cjk-space-formatter

A formatter that removes unnecessary spaces between CJK characters and math expressions / English words. LLMs (Claude, ChatGPT, etc.) tend to insert these spaces when generating Japanese text, carrying over English spacing conventions.

Primarily targets Typst files, but also works with Markdown and other formats using `$...$` inline math.

## Before / After

```
# Before (LLM-generated text)
任意の2量子ビットユニタリゲート $U in S U(4)$ を以下のように分解する：
正準パラメータは Weyl chamber $pi / 4 >= c_x$ に制限できる。

# After
任意の2量子ビットユニタリゲート$U in S U(4)$を以下のように分解する：
正準パラメータはWeyl chamber $pi / 4 >= c_x$に制限できる。
```

## Installation

```bash
uv tool install git+https://github.com/ultimatile/cjk-space-formatter
```

For development:

```bash
git clone https://github.com/ultimatile/cjk-space-formatter
cd cjk-space-formatter
uv sync --dev
```

## Usage

```bash
# Print formatted output to stdout
cjk-space-formatter file.typ

# Modify files in place
cjk-space-formatter -i file.typ

# Show unified diff of changes
cjk-space-formatter --diff file.typ

# Check only (exit 1 if changes needed, useful for CI)
cjk-space-formatter --check file.typ

# Multiple files
cjk-space-formatter -i *.typ

# Read from stdin
cat file.typ | cjk-space-formatter
```

## Rules

### Spaces removed

| Pattern | Before | After |
|---|---|---|
| CJK + space + `$` (math start) | `行列 $A$` | `行列$A$` |
| `$` (math end) + space + CJK | `$A$ の` | `$A$の` |
| CJK + space + English word | `は Weyl` | `はWeyl` |
| English word + space + CJK | `chamber の` | `chamberの` |
| CJK + space + digit | `最大 3 個` | `最大3個` |

### Spaces preserved

| Pattern | Example | Reason |
|---|---|---|
| Between English words | `Weyl chamber` | English spacing |
| Inside math `$...$` | `$A times.o B$` | Math content |
| Block math lines | `$ U = A B $` | Multi-line equations |
| Typst structural syntax | `= `, `== `, `- `, `+ ` | Headings, list markers |
| Ordered-list marker before CJK | `## 1. 項目` | Numbered marker at line start / under heading or bullet |
| After half-width colon | `注: これは` | Colon-space convention |
| After `#` before CJK | `# 見出し` | Markdown headings / Typst commands |
| After Typst `#expr` | `#sym.ballot 基底` | Space terminates expression |
| After Typst `@label` | `@eq:cost の計算` | Space terminates label reference |

## Library API

```python
from cjk_space_formatter import format_text, format_line, format_file
from pathlib import Path

# Format a string
result = format_text("テスト $x$ です")
# -> "テスト$x$です"

# Format a file in place
format_file(Path("file.typ"), in_place=True)

# Check only (returns True if changes needed)
changed = format_file(Path("file.typ"), check=True)
```

## Development

```bash
uv run --dev pytest tests/ -v
```

## License

MIT
