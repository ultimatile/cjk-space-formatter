//! Remove spaces next to CJK characters from Typst source.
//!
//! [`format()`] returns its input with some U+0020 deleted and every other byte
//! unchanged. A run of U+0020 is a candidate when it is markup prose (a
//! `Space` or part of a `Text` whose parent is `Markup`) and the characters on
//! each side satisfy the rule in the `rule` module. Candidates are deleted only
//! as a set whose removal leaves the source parsing to the same `shape`.

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
    // The candidates of each line are first checked on the line's own source;
    // the ones kept there are then checked on the whole text.
    let mut kept = Vec::new();
    for (line, group) in by_line(&root, text.len(), &candidates) {
        let source = &text[line.clone()];
        let local: Vec<_> = group
            .iter()
            .map(|run| run.start - line.start..run.end - line.start)
            .collect();
        for run in accept(source, &shape(&parse(source)), &local) {
            kept.push(run.start + line.start..run.end + line.start);
        }
    }
    let accepted = accept(text, &shape(&root), &kept);
    if accepted.is_empty() {
        return None;
    }
    Some(delete(text, &accepted))
}

/// The runs of U+0020 in markup prose that the rule removes, in source order.
fn candidates(root: &SyntaxNode, text: &str) -> Vec<Range<usize>> {
    fn walk(node: &LinkedNode, spaces: &mut Vec<Range<usize>>) {
        let mut children = node.children().peekable();
        if children.peek().is_some() {
            for child in children {
                walk(&child, spaces);
            }
            return;
        }
        let prose = node.parent_kind() == Some(SyntaxKind::Markup);
        if prose && matches!(node.kind(), SyntaxKind::Space | SyntaxKind::Text) {
            let start = node.range().start;
            for run in rule::space_runs(node.get().leaf_text()) {
                spaces.push(start + run.start..start + run.end);
            }
        }
    }

    let mut spaces = Vec::new();
    walk(&LinkedNode::new(root), &mut spaces);
    spaces.retain(|run| rule::removable_in(text, run));
    spaces
}

/// `candidates` grouped by the top-level line they lie in.
///
/// A line here runs from the end of a top-level `Space` or `Parbreak` leaf
/// that contains a newline to the end of the next one, or to an edge of the
/// text, so a node spanning several source lines stays in one piece. Each item
/// is the line's byte range and its candidates.
fn by_line<'a>(
    root: &SyntaxNode,
    len: usize,
    candidates: &'a [Range<usize>],
) -> Vec<(Range<usize>, &'a [Range<usize>])> {
    let mut starts = vec![0];
    for child in LinkedNode::new(root).children() {
        let breaks = matches!(child.kind(), SyntaxKind::Space | SyntaxKind::Parbreak)
            && child.get().leaf_text().contains('\n');
        if breaks {
            starts.push(child.range().end);
        }
    }
    let mut groups = Vec::new();
    let mut rest = candidates;
    for (i, &start) in starts.iter().enumerate() {
        let end = starts.get(i + 1).copied().unwrap_or(len);
        let count = rest.partition_point(|run| run.start < end);
        let (group, tail) = rest.split_at(count);
        rest = tail;
        if !group.is_empty() {
            groups.push((start..end, group));
        }
    }
    assert!(rest.is_empty());
    groups
}

#[derive(Debug, PartialEq, Eq)]
enum Token {
    Open(SyntaxKind),
    Close,
    Leaf(SyntaxKind, String),
    /// Consecutive `Text` leaves of one `Markup`, without their U+0020.
    Prose(String),
    /// A smart quote, and whether the prose before it ends in whitespace.
    Quote(String, bool),
    /// A label, and the `Text` leaf of the same `Markup` that it follows with
    /// only `Space` leaves in between, without its U+0020.
    Label(String, Option<String>),
}

/// What Typst reads from the prose before a leaf, beyond the tree.
struct Before {
    /// Whether the last `Text`, `Space` or `Parbreak` leaf of markup prose
    /// ends in whitespace. The start of the text counts as whitespace.
    space: bool,
    /// The last `Text` leaf of markup prose, without its U+0020, when only
    /// `Space` leaves have followed it and the node holding it has not closed.
    text: Option<String>,
}

/// The tree with the U+0020 taken out of its markup prose.
///
/// Inner nodes keep their kind and nesting, and leaves their kind and text,
/// with two exceptions under a `Markup` parent: a `Space` leaf that is only
/// U+0020 is left out, and `Text` leaves lose their U+0020 and merge with the
/// `Text` before them when nothing else is in between.
///
/// Two leaves also carry what precedes them, because Typst reads it when it
/// lays the document out: a smart quote opens or closes by the character
/// before it, and a label attaches to the element before it.
fn shape(root: &SyntaxNode) -> Vec<Token> {
    fn walk(
        node: &SyntaxNode,
        parent: Option<SyntaxKind>,
        before: &mut Before,
        out: &mut Vec<Token>,
    ) {
        let kind = node.kind();
        if node.children().len() > 0 {
            out.push(Token::Open(kind));
            for child in node.children() {
                walk(child, Some(kind), before, out);
            }
            out.push(Token::Close);
            // A label after the node follows the node, not the text in it.
            before.text = None;
            return;
        }
        let text = node.leaf_text();
        let prose = parent == Some(SyntaxKind::Markup);
        if prose && kind == SyntaxKind::Space {
            before.space = true;
            if !text.bytes().all(|b| b == b' ') {
                out.push(Token::Leaf(kind, text.to_string()));
            }
            return;
        }
        if prose && kind == SyntaxKind::Text {
            if let Some(last) = text.chars().next_back() {
                before.space = last.is_whitespace();
            }
            let text = text.as_str().replace(' ', "");
            before.text = Some(text.clone());
            match out.last_mut() {
                Some(Token::Prose(last)) => last.push_str(&text),
                _ if text.is_empty() => {}
                _ => out.push(Token::Prose(text)),
            }
            return;
        }
        if kind == SyntaxKind::Label {
            out.push(Token::Label(text.to_string(), before.text.take()));
            return;
        }
        before.text = None;
        match kind {
            SyntaxKind::Parbreak => {
                before.space = true;
                out.push(Token::Leaf(kind, text.to_string()));
            }
            SyntaxKind::SmartQuote => out.push(Token::Quote(text.to_string(), before.space)),
            _ => out.push(Token::Leaf(kind, text.to_string())),
        }
    }

    let mut out = Vec::new();
    let mut before = Before {
        space: true,
        text: None,
    };
    walk(root, None, &mut before, &mut out);
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
