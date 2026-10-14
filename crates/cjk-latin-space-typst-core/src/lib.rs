//! Remove spaces next to CJK characters from Typst source.
//!
//! [`format()`] returns its input with some U+0020 deleted and every other byte
//! unchanged. A run of U+0020 is a candidate when it is markup prose (a
//! `Space` or part of a `Text` whose parent is `Markup`) and the characters on
//! each side satisfy the rule in the `rule` module, unless it sits directly
//! before a smart quote. Candidates are deleted only as a set whose removal
//! leaves the source parsing to the same `shape`.

mod rule;

use std::collections::{BTreeMap, HashMap};
use std::fmt;
use std::ops::Range;

use typst_syntax::{Lines, LinkedNode, SyntaxKind, SyntaxNode};

#[cfg(test)]
thread_local! {
    /// Bytes handed to `parse` on this thread.
    static PARSED: std::cell::Cell<usize> = const { std::cell::Cell::new(0) };
}

fn parse(text: &str) -> SyntaxNode {
    #[cfg(test)]
    PARSED.with(|parsed| parsed.set(parsed.get() + text.len()));
    typst_syntax::parse(text)
}

const BOM: &str = "\u{feff}";

/// One syntax error reported by the Typst parser.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SyntaxError {
    line: usize,
    message: String,
}

impl SyntaxError {
    /// The 1-based line of the error in the source. Lines end where Typst
    /// ends them, with `\r\n` as one line break.
    pub fn line(&self) -> usize {
        self.line
    }

    /// The parser's message.
    pub fn message(&self) -> &str {
        &self.message
    }
}

/// The syntax errors of a source, in source order. Never empty.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SyntaxErrors(Vec<SyntaxError>);

impl SyntaxErrors {
    /// The errors, in source order.
    pub fn iter(&self) -> impl Iterator<Item = &SyntaxError> {
        self.0.iter()
    }
}

impl fmt::Display for SyntaxErrors {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for (i, error) in self.0.iter().enumerate() {
            if i > 0 {
                f.write_str("; ")?;
            }
            write!(f, "line {}: {}", error.line, error.message)?;
        }
        Ok(())
    }
}

impl std::error::Error for SyntaxErrors {}

/// `source` with the CJK-adjacent spaces of its markup prose removed.
///
/// The result is `source` with some U+0020 deleted. It parses to the same
/// tree as `source` once the U+0020 of markup prose is ignored, and `format`
/// of the result returns it unchanged. A leading BOM is set aside while
/// parsing and kept in the result.
///
/// # Errors
///
/// Returns the parser's errors when `source` has a syntax error.
pub fn format(source: &str) -> Result<String, SyntaxErrors> {
    let (bom, body) = match source.strip_prefix(BOM) {
        Some(body) => (BOM, body),
        None => ("", source),
    };
    if let Some(errors) = syntax_errors(&parse(body), body) {
        return Err(errors);
    }
    let mut memo = HashMap::new();
    let text = fixpoint(body.to_owned(), |text| pass(text, &mut memo));
    Ok(format!("{bom}{text}"))
}

/// `text` after applying `pass` until it returns `None`.
///
/// `pass` must return a shorter text or `None`.
fn fixpoint(mut text: String, mut pass: impl FnMut(&str) -> Option<String>) -> String {
    while let Some(out) = pass(&text) {
        assert!(out.len() < text.len());
        text = out;
    }
    text
}

fn syntax_errors(root: &SyntaxNode, text: &str) -> Option<SyntaxErrors> {
    fn walk(node: &LinkedNode, lines: &Lines<&str>, out: &mut Vec<SyntaxError>) {
        if node.kind() == SyntaxKind::Error {
            let (errors, _) = node.get().errors_and_warnings();
            let line = lines.byte_to_line(node.range().start).expect("in the text") + 1;
            for error in errors {
                out.push(SyntaxError {
                    line,
                    message: error.message.to_string(),
                });
            }
        }
        for child in node.children() {
            walk(&child, lines, out);
        }
    }

    let (errors, _) = root.errors_and_warnings();
    if errors.is_empty() {
        return None;
    }
    let mut found = Vec::new();
    walk(&LinkedNode::new(root), &Lines::new(text), &mut found);
    assert_eq!(
        found.len(),
        errors.len(),
        "an error is not on an `Error` node"
    );
    Some(SyntaxErrors(found))
}

/// The runs kept on a line's source alone, by the source and its candidate
/// runs, so that a line unchanged since an earlier round is not checked again.
type Memo = HashMap<(String, Vec<Range<usize>>), Vec<Range<usize>>>;

/// One round of deletions, or `None` when the round deletes nothing.
fn pass(text: &str, memo: &mut Memo) -> Option<String> {
    let root = parse(text);
    let lines = lines(&root, text);
    // Each candidate is first checked on the source of the innermost line
    // around it that parses alone to what that line is in the whole text.
    // The ones kept there, and those with no such line, are then checked on
    // the whole text.
    let mut alone = vec![Alone::Unchecked; lines.len()];
    let mut by_line: BTreeMap<usize, Vec<Range<usize>>> = BTreeMap::new();
    let mut kept = Vec::new();
    for (i, line) in lines.iter().enumerate() {
        if line.runs.is_empty() {
            continue;
        }
        let mut at = Some(i);
        while let Some(j) = at {
            if let Alone::Unchecked = alone[j] {
                let local = shape(&parse(&text[lines[j].range.clone()]));
                alone[j] = if local == lines[j].shape() {
                    Alone::Same(local)
                } else {
                    Alone::Differs
                };
            }
            if let Alone::Same(_) = alone[j] {
                break;
            }
            at = lines[j].outer;
        }
        match at {
            Some(j) => by_line
                .entry(j)
                .or_default()
                .extend(line.runs.iter().cloned()),
            None => kept.extend(line.runs.iter().cloned()),
        }
    }
    for (j, mut runs) in by_line {
        runs.sort_by_key(|run| run.start);
        let start = lines[j].range.start;
        let source = &text[lines[j].range.clone()];
        let local: Vec<_> = runs
            .iter()
            .map(|run| run.start - start..run.end - start)
            .collect();
        let Alone::Same(local_shape) = std::mem::replace(&mut alone[j], Alone::Unchecked) else {
            unreachable!("only a line that parses alone collects runs");
        };
        let accepted = memo
            .entry((source.to_owned(), local.clone()))
            .or_insert_with(|| accept(source, &local_shape, &local));
        kept.extend(
            accepted
                .iter()
                .map(|run| run.start + start..run.end + start),
        );
    }
    if kept.is_empty() {
        return None;
    }
    kept.sort_by_key(|run| run.start);
    let accepted = accept(text, &shape(&root), &kept);
    if accepted.is_empty() {
        return None;
    }
    Some(delete(text, &accepted))
}

/// How a line's source parses on its own.
#[derive(Clone)]
enum Alone {
    Unchecked,
    /// To a `shape` other than the line's in the whole text.
    Differs,
    /// To the line's `shape` in the whole text, which this is.
    Same(Vec<Token>),
}

/// A stretch of one `Markup` node's children that ends with a `Space` or
/// `Parbreak` child containing a line break, or with the node, so a child
/// spanning several source lines stays in one piece.
struct Line {
    range: Range<usize>,
    children: Vec<SyntaxNode>,
    /// Candidate runs, in source order.
    runs: Vec<Range<usize>>,
    /// The line of the enclosing `Markup` that holds this line's node.
    outer: Option<usize>,
}

impl Line {
    /// The `shape` of the children, as a `Markup` of their own.
    fn shape(&self) -> Vec<Token> {
        let mut out = vec![Token::Open(SyntaxKind::Markup)];
        for child in &self.children {
            shape_into(child, Some(SyntaxKind::Markup), &mut out);
        }
        out.push(Token::Close);
        out
    }
}

/// Every line of `root`, outer lines before the lines nested in them, with
/// the runs of U+0020 in markup prose that the rule removes and that do not
/// sit directly before a smart quote.
fn lines(root: &SyntaxNode, text: &str) -> Vec<Line> {
    struct Walk {
        lines: Vec<Line>,
        quotes: Vec<usize>,
    }

    fn open(out: &mut Walk, start: usize, outer: Option<usize>) -> usize {
        out.lines.push(Line {
            range: start..start,
            children: Vec::new(),
            runs: Vec::new(),
            outer,
        });
        out.lines.len() - 1
    }

    fn walk(node: &LinkedNode, outer: Option<usize>, out: &mut Walk) {
        if node.kind() == SyntaxKind::SmartQuote {
            out.quotes.push(node.range().start);
        }
        if node.kind() != SyntaxKind::Markup {
            for child in node.children() {
                walk(&child, outer, out);
            }
            return;
        }
        let mut line = open(out, node.range().start, outer);
        for child in node.children() {
            out.lines[line].children.push(child.get().clone());
            let leaf = child.get().leaf_text();
            match child.kind() {
                SyntaxKind::Space | SyntaxKind::Text => {
                    let offset = child.range().start;
                    for run in rule::space_runs(leaf) {
                        out.lines[line]
                            .runs
                            .push(offset + run.start..offset + run.end);
                    }
                }
                _ => walk(&child, Some(line), out),
            }
            let breaks = matches!(child.kind(), SyntaxKind::Space | SyntaxKind::Parbreak)
                && leaf.chars().any(typst_syntax::is_newline);
            if breaks {
                let end = child.range().end;
                out.lines[line].range.end = end;
                line = open(out, end, outer);
            }
        }
        out.lines[line].range.end = node.range().end;
    }

    let mut out = Walk {
        lines: Vec::new(),
        quotes: Vec::new(),
    };
    walk(&LinkedNode::new(root), None, &mut out);
    out.quotes.sort_unstable();
    for line in &mut out.lines {
        // Whether a quote opens or closes depends on the character before it,
        // which the tree does not record.
        line.runs.retain(|run| {
            rule::removable_in(text, run) && out.quotes.binary_search(&run.end).is_err()
        });
    }
    out.lines
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum Token {
    Open(SyntaxKind),
    Close,
    Leaf(SyntaxKind, String),
    /// Consecutive `Text` leaves of one `Markup`, without their U+0020.
    Prose(String),
}

/// The tree with the U+0020 taken out of its markup prose.
///
/// Inner nodes keep their kind and nesting, and leaves their kind and text,
/// with two exceptions under a `Markup` parent: a `Space` leaf that is only
/// U+0020 is left out, and `Text` leaves lose their U+0020 and merge with the
/// `Text` before them when nothing else is in between.
fn shape(root: &SyntaxNode) -> Vec<Token> {
    let mut out = Vec::new();
    shape_into(root, None, &mut out);
    out
}

/// Append the `shape` of `node`, whose parent has kind `parent`, to `out`.
fn shape_into(node: &SyntaxNode, parent: Option<SyntaxKind>, out: &mut Vec<Token>) {
    let kind = node.kind();
    if node.children().len() > 0 {
        out.push(Token::Open(kind));
        for child in node.children() {
            shape_into(child, Some(kind), out);
        }
        out.push(Token::Close);
        return;
    }
    let text = node.leaf_text();
    let prose = parent == Some(SyntaxKind::Markup);
    if prose && kind == SyntaxKind::Space && text.bytes().all(|b| b == b' ') {
        return;
    }
    if prose && kind == SyntaxKind::Text {
        let text = text.as_str().replace(' ', "");
        match out.last_mut() {
            Some(Token::Prose(last)) => last.push_str(&text),
            _ if text.is_empty() => {}
            _ => out.push(Token::Prose(text)),
        }
        return;
    }
    out.push(Token::Leaf(kind, text.to_string()));
}

/// The candidates whose deletion keeps `text` at `shape`, in source order.
///
/// The candidates are tried together. A batch that changes the shape is
/// halved until each half keeps it or is a single candidate, which is then
/// dropped. Every trial deletes the batch together with what was accepted
/// before it, so the returned set as a whole keeps the shape.
fn accept(text: &str, shape: &[Token], candidates: &[Range<usize>]) -> Vec<Range<usize>> {
    fn try_batch(
        text: &str,
        shape: &[Token],
        batch: &[Range<usize>],
        accepted: &mut Vec<Range<usize>>,
    ) {
        let mut trial = accepted.clone();
        trial.extend_from_slice(batch);
        trial.sort_by_key(|run| run.start);
        if self::shape(&parse(&delete(text, &trial))) == shape {
            *accepted = trial;
        } else if batch.len() > 1 {
            let (first, second) = batch.split_at(batch.len() / 2);
            try_batch(text, shape, first, accepted);
            try_batch(text, shape, second, accepted);
        }
    }

    let mut accepted = Vec::new();
    try_batch(text, shape, candidates, &mut accepted);
    accepted
}

/// `text` without `runs`, which must be sorted, disjoint runs of U+0020.
fn delete(text: &str, runs: &[Range<usize>]) -> String {
    let bytes = text.as_bytes();
    let mut end = 0;
    for run in runs {
        assert!(end <= run.start && run.start < run.end && run.end <= bytes.len());
        assert!(bytes[run.clone()].iter().all(|&b| b == b' '));
        end = run.end;
    }
    let mut out = String::with_capacity(text.len());
    let mut last = 0;
    for run in runs {
        out.push_str(&text[last..run.start]);
        last = run.end;
    }
    out.push_str(&text[last..]);
    out
}

#[cfg(test)]
mod tests;
