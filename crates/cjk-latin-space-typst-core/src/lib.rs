//! Remove spaces next to CJK characters from Typst source.
//!
//! [`format()`] returns its input with some U+0020 deleted and every other byte
//! unchanged. A run of U+0020 is a candidate when it is markup prose (a
//! `Space` or part of a `Text` whose parent is `Markup`), the characters on
//! each side satisfy the rule in the `rule` module, and it does not sit
//! directly before a smart quote. Candidates are deleted only as a set whose
//! removal leaves the source parsing to the same `shape`.

mod rule;

use std::fmt;
use std::ops::Range;

use typst_syntax::{LinkedNode, SyntaxKind, SyntaxNode, parse};

const BOM: &str = "\u{feff}";

/// One syntax error reported by the Typst parser.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SyntaxError {
    line: usize,
    message: String,
}

impl SyntaxError {
    /// The 1-based line of the error in the source, counted at LF.
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
    Ok(format!("{bom}{}", fixpoint(body.to_owned(), pass)))
}

/// `text` after applying `pass` until it returns `None`.
///
/// `pass` must return a shorter text or `None`.
fn fixpoint(mut text: String, pass: impl Fn(&str) -> Option<String>) -> String {
    while let Some(out) = pass(&text) {
        assert!(out.len() < text.len());
        text = out;
    }
    text
}

fn syntax_errors(root: &SyntaxNode, text: &str) -> Option<SyntaxErrors> {
    fn walk(node: &LinkedNode, text: &str, out: &mut Vec<SyntaxError>) {
        if node.kind() == SyntaxKind::Error {
            let (errors, _) = node.get().errors_and_warnings();
            let line = text[..node.range().start].matches('\n').count() + 1;
            for error in errors {
                out.push(SyntaxError {
                    line,
                    message: error.message.to_string(),
                });
            }
        }
        for child in node.children() {
            walk(&child, text, out);
        }
    }

    let (errors, _) = root.errors_and_warnings();
    if errors.is_empty() {
        return None;
    }
    let mut found = Vec::new();
    walk(&LinkedNode::new(root), text, &mut found);
    assert_eq!(
        found.len(),
        errors.len(),
        "an error is not on an `Error` node"
    );
    Some(SyntaxErrors(found))
}

/// One round of deletions, or `None` when the round deletes nothing.
fn pass(text: &str) -> Option<String> {
    let root = parse(text);
    let candidates = candidates(&root, text);
    if candidates.is_empty() {
        return None;
    }
    let accepted = accept(text, &shape(&root), &candidates);
    if accepted.is_empty() {
        return None;
    }
    Some(delete(text, &accepted))
}

/// The runs of U+0020 in markup prose that the rule removes and that do not
/// sit directly before a smart quote, in source order.
fn candidates(root: &SyntaxNode, text: &str) -> Vec<Range<usize>> {
    fn walk(node: &LinkedNode, spaces: &mut Vec<Range<usize>>, quotes: &mut Vec<usize>) {
        let mut children = node.children().peekable();
        if children.peek().is_some() {
            for child in children {
                walk(&child, spaces, quotes);
            }
            return;
        }
        let start = node.range().start;
        match node.kind() {
            SyntaxKind::SmartQuote => quotes.push(start),
            SyntaxKind::Space | SyntaxKind::Text
                if node.parent_kind() == Some(SyntaxKind::Markup) =>
            {
                for run in rule::space_runs(node.get().leaf_text()) {
                    spaces.push(start + run.start..start + run.end);
                }
            }
            _ => {}
        }
    }

    let mut spaces = Vec::new();
    let mut quotes = Vec::new();
    walk(&LinkedNode::new(root), &mut spaces, &mut quotes);
    spaces.retain(|run| {
        let prev = text[..run.start].chars().next_back();
        let next = text[run.end..].chars().next();
        // Whether a quote opens or closes depends on the character before it,
        // and the tree records neither.
        rule::removable(prev, next) && quotes.binary_search(&run.end).is_err()
    });
    spaces
}

#[derive(Debug, PartialEq, Eq)]
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
    fn walk(node: &SyntaxNode, parent: Option<SyntaxKind>, out: &mut Vec<Token>) {
        let kind = node.kind();
        if node.children().len() > 0 {
            out.push(Token::Open(kind));
            for child in node.children() {
                walk(child, Some(kind), out);
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

    let mut out = Vec::new();
    walk(root, None, &mut out);
    out
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
