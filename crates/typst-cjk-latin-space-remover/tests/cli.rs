//! Runs the built binary.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const BIN: &str = env!("CARGO_BIN_EXE_typst-cjk-latin-space-remover");

struct Output {
    status: i32,
    stdout: String,
    stderr: String,
}

/// Run the CLI in `dir`. `stdin` is piped when given and empty otherwise.
fn run(dir: &Path, args: &[&str], stdin: Option<&[u8]>) -> Output {
    let mut child = Command::new(BIN)
        .args(args)
        .current_dir(dir)
        .stdin(if stdin.is_some() {
            Stdio::piped()
        } else {
            Stdio::null()
        })
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    if let Some(data) = stdin {
        child.stdin.take().unwrap().write_all(data).unwrap();
    }
    let out = child.wait_with_output().unwrap();
    Output {
        status: out.status.code().unwrap(),
        stdout: String::from_utf8(out.stdout).unwrap(),
        stderr: String::from_utf8(out.stderr).unwrap(),
    }
}

#[track_caller]
fn assert_starts_with(text: &str, prefix: &str) {
    assert!(
        text.starts_with(prefix),
        "{text:?} does not start with {prefix:?}"
    );
}

/// A fresh directory named `name` under the test's temporary directory.
fn dir(name: &str) -> PathBuf {
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(name);
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn stdin_is_a_filter() {
    let d = dir("stdin_is_a_filter");
    let out = run(&d, &[], Some("日本 English\n".as_bytes()));
    assert_eq!(
        (out.status, out.stdout.as_str(), out.stderr.as_str()),
        (0, "日本English\n", "")
    );

    // `-i` has no file to write, so the result is still printed.
    let out = run(&d, &["-i"], Some("日本 English\n".as_bytes()));
    assert_eq!((out.status, out.stdout.as_str()), (0, "日本English\n"));
}

#[test]
fn stdin_check_reports_by_status_only() {
    let d = dir("stdin_check_reports_by_status_only");
    let out = run(&d, &["--check"], Some("日本 English\n".as_bytes()));
    assert_eq!(
        (out.status, out.stdout.as_str(), out.stderr.as_str()),
        (1, "", "")
    );
    let out = run(&d, &["--check"], Some("日本English\n".as_bytes()));
    assert_eq!(
        (out.status, out.stdout.as_str(), out.stderr.as_str()),
        (0, "", "")
    );
}

#[test]
fn stdin_errors_exit_with_2() {
    let d = dir("stdin_errors_exit_with_2");
    let out = run(&d, &[], Some(b"\xff\xfe"));
    assert_eq!((out.status, out.stdout.as_str()), (2, ""));
    assert_starts_with(&out.stderr, "error: <stdin> is not valid UTF-8: ");

    let out = run(&d, &[], Some("本文 abc\n未閉 $ x".as_bytes()));
    assert_eq!((out.status, out.stdout.as_str()), (2, ""));
    assert_eq!(out.stderr, "error: <stdin>: line 2: unclosed delimiter\n");
}

#[test]
fn without_a_flag_every_file_is_printed() {
    let d = dir("without_a_flag_every_file_is_printed");
    fs::write(d.join("a.typ"), "日本 English\n").unwrap();
    fs::write(d.join("b.typ"), "unchanged text\n").unwrap();
    let out = run(&d, &["a.typ", "b.typ"], None);
    assert_eq!(
        (out.status, out.stdout.as_str()),
        (0, "日本English\nunchanged text\n")
    );
    assert_eq!(
        fs::read_to_string(d.join("a.typ")).unwrap(),
        "日本 English\n"
    );
}

#[test]
fn in_place_rewrites_changed_files_and_keeps_every_other_byte() {
    let d = dir("in_place_rewrites_changed_files");
    fs::write(d.join("crlf.typ"), "\u{feff}日本 English\r\nテスト です").unwrap();
    fs::write(d.join("same.typ"), "unchanged text\n").unwrap();
    let out = run(&d, &["-i", "crlf.typ", "same.typ"], None);
    assert_eq!(
        (out.status, out.stdout.as_str()),
        (0, "reformatted crlf.typ\n")
    );
    assert_eq!(
        fs::read(d.join("crlf.typ")).unwrap(),
        "\u{feff}日本English\r\nテストです".as_bytes()
    );
    assert_eq!(
        fs::read_to_string(d.join("same.typ")).unwrap(),
        "unchanged text\n"
    );
}

#[test]
fn check_names_the_files_that_would_change() {
    let d = dir("check_names_the_files_that_would_change");
    fs::write(d.join("a.typ"), "日本 English\n").unwrap();
    fs::write(d.join("b.typ"), "unchanged text\n").unwrap();
    let out = run(&d, &["--check", "a.typ", "b.typ"], None);
    assert_eq!(
        (out.status, out.stdout.as_str()),
        (1, "would reformat a.typ\n")
    );
    let out = run(&d, &["--check", "b.typ"], None);
    assert_eq!((out.status, out.stdout.as_str()), (0, ""));
}

#[test]
fn check_wins_over_diff_which_wins_over_in_place() {
    let d = dir("check_wins_over_diff");
    let source = "日本 English\n";
    fs::write(d.join("a.typ"), source).unwrap();

    let out = run(&d, &["--check", "--diff", "a.typ"], None);
    assert_eq!(
        (out.status, out.stdout.as_str()),
        (1, "would reformat a.typ\n")
    );

    let out = run(&d, &["--check", "-i", "a.typ"], None);
    assert_eq!(
        (out.status, out.stdout.as_str()),
        (1, "would reformat a.typ\n")
    );
    assert_eq!(fs::read_to_string(d.join("a.typ")).unwrap(), source);

    let out = run(&d, &["--diff", "--in-place", "a.typ"], None);
    assert_eq!(out.status, 0);
    assert_starts_with(&out.stdout, "--- a/a.typ\n+++ b/a.typ\n");
    assert_eq!(fs::read_to_string(d.join("a.typ")).unwrap(), source);
}

#[test]
fn diff_is_a_unified_diff() {
    let d = dir("diff_is_a_unified_diff");
    let lines: Vec<String> = (1..=12).map(|i| format!("line {i}\n")).collect();
    let mut source = lines.clone();
    source[1] = "日本 English\n".into();
    source[10] = "テスト です\n".into();
    fs::write(d.join("a.typ"), source.concat()).unwrap();
    let out = run(&d, &["--diff", "a.typ"], None);
    assert_eq!(out.status, 0);
    assert_eq!(
        out.stdout,
        "--- a/a.typ\n+++ b/a.typ\n\
         @@ -1,5 +1,5 @@\n line 1\n-日本 English\n+日本English\n line 3\n line 4\n line 5\n\
         @@ -8,5 +8,5 @@\n line 8\n line 9\n line 10\n-テスト です\n+テストです\n line 12\n"
    );

    // Six unchanged lines lie between the changes, so their context windows
    // touch and the two share a hunk.
    let mut source = lines.clone();
    source[1] = "日本 English\n".into();
    source[8] = "テスト です\n".into();
    fs::write(d.join("b.typ"), source.concat()).unwrap();
    let out = run(&d, &["--diff", "b.typ"], None);
    assert_eq!(
        out.stdout,
        "--- a/b.typ\n+++ b/b.typ\n\
         @@ -1,12 +1,12 @@\n line 1\n-日本 English\n+日本English\n\
         \x20line 3\n line 4\n line 5\n line 6\n line 7\n line 8\n\
         -テスト です\n+テストです\n line 10\n line 11\n line 12\n"
    );

    fs::write(d.join("same.typ"), "unchanged text\n").unwrap();
    let out = run(&d, &["--diff", "same.typ"], None);
    assert_eq!((out.status, out.stdout.as_str()), (0, ""));
}

#[test]
fn diff_marks_a_missing_final_newline() {
    let d = dir("diff_marks_a_missing_final_newline");
    fs::write(d.join("a.typ"), "日本 English").unwrap();
    let out = run(&d, &["--diff", "a.typ"], None);
    assert_eq!(
        out.stdout,
        "--- a/a.typ\n+++ b/a.typ\n@@ -1 +1 @@\n\
         -日本 English\n\\ No newline at end of file\n\
         +日本English\n\\ No newline at end of file\n"
    );

    let out = run(&d, &["--diff"], Some("前 text\n日本 English".as_bytes()));
    assert_eq!(
        out.stdout,
        "--- a/<stdin>\n+++ b/<stdin>\n@@ -1,2 +1,2 @@\n\
         -前 text\n-日本 English\n\\ No newline at end of file\n\
         +前text\n+日本English\n\\ No newline at end of file\n"
    );
}

#[test]
fn a_file_that_cannot_be_formatted_exits_with_2() {
    let d = dir("a_file_that_cannot_be_formatted");
    fs::create_dir(d.join("sub")).unwrap();
    fs::write(d.join("bad.typ"), b"\xff\xfe").unwrap();
    fs::write(d.join("syntax.typ"), "本文 abc\n\n#let\n未閉 $ x").unwrap();

    let out = run(&d, &["missing.typ"], None);
    assert_eq!(
        (out.status, out.stderr.as_str()),
        (2, "error: missing.typ not found\n")
    );

    let out = run(&d, &["sub"], None);
    assert_eq!(
        (out.status, out.stderr.as_str()),
        (2, "error: sub is a directory\n")
    );

    let out = run(&d, &["bad.typ"], None);
    assert_eq!(out.status, 2);
    assert_starts_with(&out.stderr, "error: bad.typ is not valid UTF-8: ");

    let out = run(&d, &["syntax.typ"], None);
    assert_eq!((out.status, out.stdout.as_str()), (2, ""));
    assert_eq!(
        out.stderr,
        "error: syntax.typ: line 3: expected pattern\n\
         error: syntax.typ: line 4: unclosed delimiter\n"
    );

    // A lone `-` is a file name, not a flag.
    let out = run(&d, &["-"], None);
    assert_eq!(
        (out.status, out.stderr.as_str()),
        (2, "error: - not found\n")
    );

    let out = run(&d, &["--bogus"], None);
    assert_eq!(
        (out.status, out.stderr.as_str()),
        (2, "error: unrecognized argument: --bogus\n")
    );
}

#[cfg(unix)]
#[test]
fn an_unreadable_file_exits_with_2() {
    use std::os::unix::fs::PermissionsExt;
    let d = dir("an_unreadable_file");
    let path = d.join("locked.typ");
    fs::write(&path, "日本 English\n").unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o000)).unwrap();
    if fs::read(&path).is_ok() {
        return; // running as a user that ignores file modes
    }
    let out = run(&d, &["locked.typ"], None);
    assert_eq!(out.status, 2);
    assert_starts_with(&out.stderr, "error: locked.typ: ");
}

#[cfg(unix)]
#[test]
fn a_failed_write_exits_with_2() {
    use std::os::unix::fs::PermissionsExt;
    let d = dir("a_failed_write");
    let path = d.join("readonly.typ");
    fs::write(&path, "日本 English\n").unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o444)).unwrap();
    if fs::OpenOptions::new().write(true).open(&path).is_ok() {
        return; // running as a user that ignores file modes
    }
    let out = run(&d, &["-i", "readonly.typ"], None);
    assert_eq!((out.status, out.stdout.as_str()), (2, ""));
    assert_starts_with(&out.stderr, "error: readonly.typ: ");
}

#[test]
fn a_double_dash_ends_the_flags() {
    let d = dir("a_double_dash_ends_the_flags");
    fs::write(d.join("--check"), "日本 English\n").unwrap();
    let out = run(&d, &["--", "--check"], None);
    assert_eq!((out.status, out.stdout.as_str()), (0, "日本English\n"));
}

#[test]
fn help_prints_the_usage() {
    let d = dir("help_prints_the_usage");
    for flag in ["-h", "--help"] {
        let out = run(&d, &[flag], None);
        assert_eq!(out.status, 0);
        assert_starts_with(&out.stdout, "usage: typst-cjk-latin-space-remover ");
    }
}

#[test]
fn nothing_is_written_when_a_later_file_fails() {
    let d = dir("nothing_is_written_when_a_later_file_fails");
    fs::write(d.join("a.typ"), "日本 English\n").unwrap();
    fs::write(d.join("z.typ"), "未閉 $ x").unwrap();
    let out = run(&d, &["-i", "a.typ", "z.typ"], None);
    assert_eq!((out.status, out.stdout.as_str()), (2, ""));
    assert_eq!(
        fs::read_to_string(d.join("a.typ")).unwrap(),
        "日本 English\n"
    );
}

#[test]
fn version_names_the_program() {
    let d = dir("version_names_the_program");
    for flag in ["-V", "--version"] {
        let out = run(&d, &[flag], None);
        assert_eq!(
            (out.status, out.stdout.as_str()),
            (
                0,
                concat!(
                    "typst-cjk-latin-space-remover ",
                    env!("CARGO_PKG_VERSION"),
                    "\n"
                )
            )
        );
    }
}
