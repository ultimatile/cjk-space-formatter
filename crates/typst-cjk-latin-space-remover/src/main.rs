//! CLI entry point for typst-cjk-latin-space-remover.
//!
//! Input and formatted output are bytes, decoded and encoded as UTF-8 with no
//! newline translation. Status and error messages are printed as text.

use std::ffi::OsString;
use std::io::{self, IsTerminal, Read, Write};
use std::path::PathBuf;
use std::process::ExitCode;

const NAME: &str = env!("CARGO_PKG_NAME");
const USAGE: &str = "\
usage: typst-cjk-latin-space-remover [-h] [-V] [--check] [-i] [--diff] [files ...]

Remove spaces next to CJK characters in Typst files

positional arguments:
  files           files to format

options:
  -h, --help      show this help message and exit
  -V, --version   show the version and exit
  --check         exit with 1 if any file would be changed
  -i, --in-place  modify files in place
  --diff          show unified diff of changes
";

#[derive(Default)]
struct Args {
    check: bool,
    in_place: bool,
    diff: bool,
    files: Vec<PathBuf>,
}

/// Error messages for stderr, one per line; the process then exits with
/// status 2.
struct Failure(Vec<String>);

impl Failure {
    fn new(message: String) -> Self {
        Self(vec![message])
    }
}

fn main() -> ExitCode {
    let mut stdout = io::stdout().lock();
    let result = run(std::env::args_os().skip(1).collect(), &mut stdout)
        .and_then(|code| stdout.flush().map_err(io_failure("stdout")).map(|()| code));
    match result {
        Ok(code) => code,
        Err(Failure(messages)) => {
            for message in messages {
                eprintln!("error: {message}");
            }
            ExitCode::from(2)
        }
    }
}

fn run(raw: Vec<OsString>, stdout: &mut io::StdoutLock) -> Result<ExitCode, Failure> {
    let mut args = Args::default();
    let mut only_files = false;
    for arg in raw {
        match arg.to_str() {
            _ if only_files => args.files.push(arg.into()),
            Some("--") => only_files = true,
            Some("-h" | "--help") => {
                print!("{USAGE}");
                return Ok(ExitCode::SUCCESS);
            }
            Some("-V" | "--version") => {
                println!("{NAME} {}", env!("CARGO_PKG_VERSION"));
                return Ok(ExitCode::SUCCESS);
            }
            Some("--check") => args.check = true,
            Some("-i" | "--in-place") => args.in_place = true,
            Some("--diff") => args.diff = true,
            Some(flag) if flag.starts_with('-') && flag != "-" => {
                return Err(Failure::new(format!("unrecognized argument: {flag}")));
            }
            _ => args.files.push(arg.into()),
        }
    }

    let write = |stdout: &mut io::StdoutLock, bytes: &[u8]| {
        stdout.write_all(bytes).map_err(io_failure("stdout"))
    };

    // stdin mode when no files are given and stdin is not a terminal
    if args.files.is_empty() {
        if io::stdin().is_terminal() {
            return Err(Failure::new(
                "no files specified (pipe to stdin or pass file paths)".into(),
            ));
        }
        let mut data = Vec::new();
        io::stdin()
            .read_to_end(&mut data)
            .map_err(io_failure("<stdin>"))?;
        let (text, formatted) = format("<stdin>", data)?;
        if args.check {
            return Ok(if text == formatted {
                ExitCode::SUCCESS
            } else {
                ExitCode::from(1)
            });
        }
        if args.diff {
            write(stdout, diff("<stdin>", &text, &formatted).as_bytes())?;
        } else {
            write(stdout, formatted.as_bytes())?;
        }
        return Ok(ExitCode::SUCCESS);
    }

    // Every file is read, decoded, and formatted before any is written.
    let mut results = Vec::new();
    for path in &args.files {
        let name = path.display().to_string();
        if !path.exists() {
            return Err(Failure::new(format!("{name} not found")));
        }
        if path.is_dir() {
            return Err(Failure::new(format!("{name} is a directory")));
        }
        let data = std::fs::read(path).map_err(io_failure(&name))?;
        let (text, formatted) = format(&name, data)?;
        results.push((path, name, text, formatted));
    }

    let mut any_changed = false;
    for (path, name, text, formatted) in results {
        let changed = text != formatted;
        any_changed |= changed;
        if args.check {
            if changed {
                write(stdout, format!("would reformat {name}\n").as_bytes())?;
            }
        } else if args.diff {
            write(stdout, diff(&name, &text, &formatted).as_bytes())?;
        } else if args.in_place {
            if changed {
                std::fs::write(path, &formatted).map_err(io_failure(&name))?;
                write(stdout, format!("reformatted {name}\n").as_bytes())?;
            }
        } else {
            // a filter: the output is the whole file, changed or not
            write(stdout, formatted.as_bytes())?;
        }
    }

    Ok(if args.check && any_changed {
        ExitCode::from(1)
    } else {
        ExitCode::SUCCESS
    })
}

/// Turns an I/O error on `name` into a [`Failure`].
fn io_failure(name: &str) -> impl Fn(io::Error) -> Failure {
    move |err| Failure::new(format!("{name}: {err}"))
}

/// The decoded input and its formatted form.
fn format(name: &str, data: Vec<u8>) -> Result<(String, String), Failure> {
    let text = String::from_utf8(data)
        .map_err(|err| Failure::new(format!("{name} is not valid UTF-8: {}", err.utf8_error())))?;
    match cjk_latin_space_typst_core::format(&text) {
        Ok(formatted) => Ok((text, formatted)),
        Err(errors) => {
            let lines: Vec<String> = errors
                .iter()
                .map(|error| format!("{name}: line {}: {}", error.line(), error.message()))
                .collect();
            Err(Failure(lines))
        }
    }
}

/// A unified diff from `old` to `new`, empty when they are equal.
///
/// `new` is `old` with spaces deleted, so both have the same lines in the
/// same order and the diff pairs them by index.
fn diff(name: &str, old: &str, new: &str) -> String {
    const CONTEXT: usize = 3;
    let old: Vec<&str> = old.split_inclusive('\n').collect();
    let new: Vec<&str> = new.split_inclusive('\n').collect();
    assert_eq!(
        old.len(),
        new.len(),
        "formatting changed the number of lines"
    );
    let changed: Vec<usize> = (0..old.len()).filter(|&i| old[i] != new[i]).collect();

    // Changed lines whose context windows touch share a hunk.
    let mut hunks: Vec<(usize, usize)> = Vec::new();
    for &i in &changed {
        let start = i.saturating_sub(CONTEXT);
        let end = (i + CONTEXT + 1).min(old.len());
        match hunks.last_mut() {
            Some(last) if start <= last.1 => last.1 = end,
            _ => hunks.push((start, end)),
        }
    }

    let mut out = String::new();
    if !hunks.is_empty() {
        out.push_str(&format!("--- a/{name}\n+++ b/{name}\n"));
    }
    let emit = |out: &mut String, sign: char, line: &str| {
        out.push(sign);
        out.push_str(line);
        if !line.ends_with('\n') {
            out.push_str("\n\\ No newline at end of file\n");
        }
    };
    for (start, end) in hunks {
        let range = match end - start {
            1 => format!("{}", start + 1),
            len => format!("{},{len}", start + 1),
        };
        out.push_str(&format!("@@ -{range} +{range} @@\n"));
        let mut i = start;
        while i < end {
            if old[i] == new[i] {
                emit(&mut out, ' ', old[i]);
                i += 1;
                continue;
            }
            let first = i;
            while i < end && old[i] != new[i] {
                i += 1;
            }
            for line in &old[first..i] {
                emit(&mut out, '-', line);
            }
            for line in &new[first..i] {
                emit(&mut out, '+', line);
            }
        }
    }
    out
}
