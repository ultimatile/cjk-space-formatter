//! The format-independent rule: which runs of U+0020 go, given the characters
//! on each side.
//!
//! This is the invariant the Python core's `squash` implements
//! (`core/src/cjk_latin_space/__init__.py`). `conformance/cases.json` is run
//! against both.

use std::ops::Range;

/// Whether `c` is in the CJK class of the Python core (`CJK_CLASS`).
pub(crate) fn is_cjk(c: char) -> bool {
    matches!(c,
        '\u{3000}'..='\u{30FF}'   // CJK symbols and punctuation, Hiragana, Katakana
        | '\u{4E00}'..='\u{9FFF}' // CJK Unified Ideographs
        | '\u{F900}'..='\u{FAFF}' // CJK Compatibility Ideographs
        | '\u{FF01}'..='\u{FF60}' // Fullwidth ASCII variants
        | '\u{FF65}'..='\u{FF9F}' // Halfwidth Katakana
    )
}

/// Whether Python's `re` matches `c` with `\s` in a `str` pattern.
///
/// `char::is_whitespace` leaves out U+001C..=U+001F.
pub(crate) fn is_py_space(c: char) -> bool {
    matches!(c,
        '\u{09}'..='\u{0D}'
        | '\u{1C}'..='\u{20}'
        | '\u{85}'
        | '\u{A0}'
        | '\u{1680}'
        | '\u{2000}'..='\u{200A}'
        | '\u{2028}'
        | '\u{2029}'
        | '\u{202F}'
        | '\u{205F}'
        | '\u{3000}'
    )
}

/// Whether a maximal run of U+0020 between `prev` and `next` is removed.
///
/// A run at the start or end of the text stays. Otherwise it goes when `prev`
/// is CJK and `next` is not whitespace, or when `prev` is neither whitespace
/// nor a half-width colon and `next` is CJK.
pub(crate) fn removable(prev: Option<char>, next: Option<char>) -> bool {
    let (Some(prev), Some(next)) = (prev, next) else {
        return false;
    };
    (is_cjk(prev) && !is_py_space(next)) || (!is_py_space(prev) && prev != ':' && is_cjk(next))
}

/// Byte ranges of the maximal runs of U+0020 in `text`, in order.
pub(crate) fn space_runs(text: &str) -> Vec<Range<usize>> {
    let bytes = text.as_bytes();
    let mut runs = Vec::new();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] != b' ' {
            i += 1;
            continue;
        }
        let start = i;
        while i < bytes.len() && bytes[i] == b' ' {
            i += 1;
        }
        runs.push(start..i);
    }
    runs
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `text` with every run removed that `removable` marks, as the Python
    /// `squash` does on a plain run.
    fn squash(text: &str) -> String {
        let mut out = String::with_capacity(text.len());
        let mut last = 0;
        for run in space_runs(text) {
            let prev = text[..run.start].chars().next_back();
            let next = text[run.end..].chars().next();
            if removable(prev, next) {
                out.push_str(&text[last..run.start]);
                last = run.end;
            }
        }
        out.push_str(&text[last..]);
        out
    }

    #[test]
    fn conformance_cases() {
        let cases: Vec<(String, String)> =
            serde_json::from_str(include_str!("../../../conformance/cases.json")).unwrap();
        assert_eq!(cases.len(), 20);
        for (input, expected) in cases {
            assert_eq!(squash(&input), expected, "input: {input:?}");
        }
    }

    #[test]
    fn whitespace_set_is_pythons() {
        let spaces: Vec<u32> = (0..=0x10FFFF)
            .filter_map(char::from_u32)
            .filter(|&c| is_py_space(c))
            .map(u32::from)
            .collect();
        let expected: Vec<u32> = [
            0x09..=0x0D,
            0x1C..=0x20,
            0x85..=0x85,
            0xA0..=0xA0,
            0x1680..=0x1680,
            0x2000..=0x200A,
            0x2028..=0x2029,
            0x202F..=0x202F,
            0x205F..=0x205F,
            0x3000..=0x3000,
        ]
        .into_iter()
        .flatten()
        .collect();
        assert_eq!(spaces, expected);
        assert_eq!(spaces.len(), 29);
    }

    #[test]
    fn cjk_class_edges() {
        for c in [
            '\u{3000}', '\u{30FF}', '\u{4E00}', '\u{9FFF}', '\u{F900}', '\u{FAFF}',
        ] {
            assert!(is_cjk(c), "{c:?}");
        }
        for c in ['\u{FF01}', '\u{FF60}', '\u{FF65}', '\u{FF9F}'] {
            assert!(is_cjk(c), "{c:?}");
        }
        for c in [
            '\u{2FFF}', '\u{3100}', '\u{4DFF}', '\u{A000}', '\u{F8FF}', '\u{FB00}',
        ] {
            assert!(!is_cjk(c), "{c:?}");
        }
        for c in [
            '\u{FF00}',
            '\u{FF61}',
            '\u{FF64}',
            '\u{FFA0}',
            '\u{20000}',
            'a',
        ] {
            assert!(!is_cjk(c), "{c:?}");
        }
    }

    #[test]
    fn space_runs_are_maximal() {
        assert_eq!(space_runs(""), vec![]);
        assert_eq!(space_runs("ab"), vec![]);
        assert_eq!(space_runs(" a  b "), vec![0..1, 2..4, 5..6]);
        assert_eq!(space_runs("日 本"), vec![3..4]);
        assert_eq!(space_runs("a\u{3000} \tb"), vec![4..5]);
    }
}
