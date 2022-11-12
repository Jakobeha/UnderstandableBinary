mod c_ast;

use std::env::args;
use std::ffi::OsStr;
use std::fs::File;
use std::io::{Seek, Write};
use rayon::iter::{ParallelBridge, ParallelIterator};
use walkdir::{DirEntry, WalkDir};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use clang_ast::SourceRange;
use regex::Regex;
use lazy_static::lazy_static;
use crate::c_ast::{Data, DoRecurse};

macro_rules! annotate_err {
    ($e:expr, $msg:expr) => {
        $e.map_err(|error| {
            eprintln!("Failed to {}", $msg);
            error
        })
    };
}

fn main() {
    let in_dir = PathBuf::from(args().nth(1).expect("Missing input directory"));
    let out_dir = PathBuf::from(args().nth(2).expect("Missing output directory"));
    let num_processed_sources = AtomicUsize::new(0);
    let num_processed_functions = AtomicUsize::new(0);
    let iter = WalkDir::new(&in_dir)
        // No need to follow symlinks
        .follow_links(false)
        .into_iter()
        // Multi-threaded (comment out for debugging, otherwise lldb loses connection)
        // .par_bridge()
        // Should not have unreadable directories
        .map(|e| e.expect("Unreadable directory"))
        .filter(|e| e.path().extension() == Some(OsStr::new("o")) && e.path().with_extension("c").exists());
    iter.for_each(|e| process(e, &in_dir, &out_dir, &num_processed_sources, &num_processed_functions));
    println!(
        "Processed {} sources and {} functions!",
        num_processed_sources.load(Ordering::Acquire),
        num_processed_functions.load(Ordering::Acquire)
    );
}

fn process(entry: DirEntry, in_dir: &Path, out_dir: &Path, num_processed_sources: &AtomicUsize, num_processed_functions: &AtomicUsize) {
    let in_obj_path = entry.into_path();
    let in_src_path = in_obj_path.with_extension("c");
    assert!(in_src_path.exists(), "Missing source file for object file {}", in_obj_path.display());
    let subpath = in_obj_path.strip_prefix(&in_dir).expect("input dir entry outside of input, security vulnerability");
    let mut out_dir = out_dir.join(subpath);
    out_dir.set_extension("");
    // Do _process, but if it fails, print and skip to process the next file.
    // Also don't keep an incomplete directory
    match _process(&in_src_path, &in_obj_path, &out_dir, &num_processed_functions) {
        Ok(_) => {
            num_processed_sources.fetch_add(1, Ordering::Release);
        },
        Err(error) => {
            eprintln!("Error processing file {}:\n\t{}", in_src_path.display(), error);
            std::fs::remove_dir_all(&out_dir).expect("Failed to remove output entry");
        }
    }
}

fn _process(in_src_path: &Path, in_obj_path: &Path, out_dir: &Path, num_processed_functions: &AtomicUsize) -> std::io::Result<()> {
    annotate_err!(std::fs::create_dir_all(out_dir), "create directory")?;

    // Copy input without includes, and objdump assembly (before breaking up these files)
    // Also parse source code via clang -ast-dump
    let out_full_assembly_temp = out_dir.join("full.s");
    let out_c_ast_temp = out_dir.join("full.c.json");
    annotate_err!(objdump(in_obj_path, &out_full_assembly_temp), "objdump")?;
    annotate_err!(parse_via_clang_ast_dump(in_src_path, &out_c_ast_temp), "clang --ast-dump")?;

    // Read C ast from dump, read C source code which the ast dump references
    let in_c = annotate_err!(c_ast::read_from_path(&out_c_ast_temp), "read C AST dump")?;
    let in_c_text = annotate_err!(std::fs::read_to_string(&in_src_path), "read C source")?;
    let in_c_lines = in_c_text.lines().collect::<Vec<_>>();

    // Break assembly into lines, allocate vector to store them
    let in_obj_text = annotate_err!(std::fs::read_to_string(&out_full_assembly_temp), "read objdump")?;
    let in_obj_lines = in_obj_text.lines().collect::<Vec<_>>();

    let process_fun = |name: &str, range: &SourceRange| {
        // spelling_loc = code position in the C source code
        // expansion_loc = after macro expansion, which we don't have and don't care about
        let start_line = range.begin.spelling_loc.as_ref().expect("clang missing function location info").line - 1;
        let end_line = range.end.spelling_loc.as_ref().expect("clang missing function location info").line - 1;
        if start_line > end_line || end_line >= in_c_lines.len() {
            Err(std::io::Error::new(std::io::ErrorKind::Other, "clang reported location out of range"))?;
        }
        let lines = &in_c_lines[start_line..=end_line];

        let fn_path = out_dir.join(name);
        let mut in_ir_file = File::create(fn_path.with_extension("s"))?;
        let mut out_ir_file = File::create(fn_path.with_extension("c"))?;
        // Like _process, don't keep one corresponding file without the other
        _process_fun(&in_obj_lines, name, lines, &mut in_ir_file, &mut out_ir_file).map_err(|error| {
            std::fs::remove_file(fn_path.with_extension("c")).expect("Failed to remove input IR file");
            std::fs::remove_file(fn_path.with_extension("s")).expect("Failed to remove output IR file");
            error
        })
    };

    // Visitor:
    //   For each declaration (training example) in the C code, extract the corresponding assembly
    //   create 2 corresponding files to store both.
    //   Also print errors but don't stop processing, just skip
    c_ast::visit(&in_c, |node| match &node.kind {
        Data::FunctionDecl { name, range, loc } => {
            // Only handle named functions in the corresponding c file (not #include'd)
            if loc.expansion_loc.is_none() || loc.expansion_loc.as_ref().unwrap().included_from.is_none() {
                if let Some(name) = name {
                    match process_fun(name, range) {
                        Ok(()) => {
                            num_processed_functions.fetch_add(1, Ordering::Release);
                        },
                        Err(error) => {
                            eprintln!("Error processing function in {}, {}:\n\t{}", in_src_path.display(), name, error);
                        }
                    }
                }
            }
            DoRecurse(false)
        }
        Data::Other => DoRecurse(true)
    });

    // Cleanup: remove objdump assembly file and clang --ast-dump source file
    //   Note that if this fails, num_processed_functions will be off,
    //   but failure is extremely likely and it's worth logging inaccuracy vs keeping bad data
    annotate_err!(std::fs::remove_file(&out_full_assembly_temp), "cleanup objdump")?;
    annotate_err!(std::fs::remove_file(&out_c_ast_temp), "cleanup clang -ast-dump")?;

    Ok(())
}

fn objdump(in_path: &Path, out_path: &Path) -> std::io::Result<()> {
    let out_file = File::create(out_path)?;
    let out_pipe = Stdio::from(out_file);

    let status = Command::new("objdump")
        .arg("-drwC")
        .arg("-Mintel")
        .arg(in_path)
        .stdout(out_pipe)
        .status()?;
    if !status.success() {
        return Err(std::io::Error::new(std::io::ErrorKind::Other, "objdump failed"));
    }
    Ok(())
}

fn clang_e(in_path: &Path, out_path: &Path) -> std::io::Result<()> {
    let out_file = File::create(out_path)?;
    let out_pipe = Stdio::from(out_file);

    let status = Command::new("clang")
        .arg("-E")
        .arg(in_path)
        .stdout(out_pipe)
        .status()?;
    if is_path_empty(out_path)? {
        return Err(std::io::Error::new(std::io::ErrorKind::Other, "clang -E failed (nothing written)"));
    }
    if !status.success() {
        eprintln!("Warning: clang -E exit code != 0 (still produced output)");
    }
    Ok(())
}

fn parse_via_clang_ast_dump(in_path: &Path, out_path: &Path) -> std::io::Result<()> {
    let out_file = File::create(out_path)?;
    let out_pipe = Stdio::from(out_file);

    let status = Command::new("clang")
        .arg("-Xclang")
        .arg("-ast-dump=json")
        .arg("-fsyntax-only")
        .arg(in_path)
        .stdout(out_pipe)
        .status()?;
    if is_path_empty(out_path)? {
        return Err(std::io::Error::new(std::io::ErrorKind::Other, "clang -ast-dump failed (nothing written)"));
    }
    if !status.success() {
        eprintln!("Warning: clang -ast-dump exit code != 0 (still produced output)");
    }
    Ok(())
}

lazy_static! {
    static ref ASM_FN_DEF_REGEX: Regex = Regex::new(r"^[0-9a-f]+ <(.+)>:$").expect("internal error: bad regex format?");
}

fn _process_fun(in_obj_lines: &[&str], fn_name: &str, c_lines: &[&str], in_ir_file: &mut File, out_ir_file: &mut File) -> std::io::Result<()> {
    write_lines(out_ir_file, c_lines)?;

    let asm_lines = in_obj_lines.iter()
        // From "0000000000000230 <name>:"
        .skip_while(|line| ASM_FN_DEF_REGEX.captures(line).map_or(true, |m| &m[1] != fn_name))
        // To empty line
        .take_while(|line| !line.is_empty());
    let num_asm_lines = write_lines(in_ir_file, asm_lines)?;
    if num_asm_lines == 0 {
        return Err(std::io::Error::new(std::io::ErrorKind::Other, "no assembly found for function (probably was inlined or dead-code)"));
    }

    Ok(())
}

fn is_path_empty(path: &Path) -> std::io::Result<bool> {
    let metadata = std::fs::metadata(path)?;
    Ok(metadata.len() == 0)
}

fn write_lines<'a>(write: &mut impl Write, lines: impl IntoIterator<Item=&'a &'a str>) -> std::io::Result<usize> {
    let mut num_lines = 0;
    for line in lines {
        writeln!(write, "{}", line)?;
        num_lines += 1;
    }
    Ok(num_lines)
}