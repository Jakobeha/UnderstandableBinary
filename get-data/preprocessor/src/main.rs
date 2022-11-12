mod io_write_to_fmt_write;
mod c_ast;

use std::env::args;
use std::ffi::OsStr;
use std::fs::File;
use std::io::Write;
use rayon::iter::{ParallelBridge, ParallelIterator};
use walkdir::{DirEntry, WalkDir};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use clang_ast::SourceRange;
use regex::Regex;
use lazy_static::lazy_static;
use crate::c_ast::{Data, DoRecurse};

fn main() {
    let in_dir = PathBuf::from(args().nth(1).expect("Missing input directory"));
    let out_dir = PathBuf::from(args().nth(2).expect("Missing output directory"));
    let num_processed = AtomicUsize::new(0);
    let iter = WalkDir::new(&in_dir)
        // No need to follow symlinks
        .follow_links(false)
        .into_iter()
        // Multi-threaded (comment out for debugging, otherwise lldb loses connection)
        // .par_bridge()
        // Should not have unreadable directories
        .map(|e| e.expect("Unreadable directory"))
        .filter(|e| e.path().extension() == Some(OsStr::new("o")) && e.path().with_extension("c").exists());
    iter.for_each(|e| process(e, &in_dir, &out_dir, &num_processed));
    println!("Processed {} sources!", num_processed.load(Ordering::Acquire));
}

fn process(entry: DirEntry, in_dir: &Path, out_dir: &Path, num_processed: &AtomicUsize) {
    let in_obj_path = entry.into_path();
    let in_src_path = in_obj_path.with_extension("c");
    assert!(in_src_path.exists(), "Missing source file for object file {}", in_obj_path.display());
    let subpath = in_obj_path.strip_prefix(&in_dir).expect("input dir entry outside of input, security vulnerability");
    let mut out_dir = out_dir.join(subpath);
    out_dir.set_extension("");
    // Do _process, but if it fails, print and skip to process the next file.
    // Also don't keep an incomplete directory
    match _process(&in_src_path, &in_obj_path, &out_dir) {
        Ok(_) => {
            num_processed.fetch_add(1, Ordering::Release);
        },
        Err(error) => {
            eprintln!("Error processing file {}:\n\t{}", in_src_path.display(), error);
            std::fs::remove_dir_all(&out_dir).expect("Failed to remove output entry");
        }
    }
}

fn _process(in_src_path: &Path, in_obj_path: &Path, out_dir: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(out_dir)?;

    // Copy input without includes, and objdump assembly (before breaking up these files)
    // Also parse source code via clang -ast-dump
    let out_full_assembly_temp = out_dir.join("full.s");
    let out_c_ast_temp = out_dir.join("full.c.json");
    objdump(in_obj_path, &out_full_assembly_temp)?;
    parse_via_clang_ast_dump(in_src_path, &out_c_ast_temp)?;

    // Read C ast from dump, read C source code ast references
    let in_c = c_ast::read_from_path(&out_c_ast_temp)?;
    let in_c_source = std::fs::read_to_string(in_src_path)?;

    // Break assembly into lines, allocate vector to store them
    let in_obj_text = std::fs::read_to_string(in_obj_path)?;
    let in_obj_lines = in_obj_text.lines().collect::<Vec<_>>();

    let process_fun = |name: &str, range: &SourceRange| {
        let start = range.begin.spelling_loc.as_ref().expect("clang missing function location info").offset;
        let end = range.end.spelling_loc.as_ref().expect("clang missing function location info").offset;
        let body = &in_c_source[start..end];

        let fn_path = out_dir.join(name);
        let mut in_ir_file = File::create(fn_path.with_extension("c"))?;
        let mut out_ir_file = File::create(fn_path.with_extension("s"))?;
        // Like _process, don't keep one corresponding file without the other
        _process_fun(&in_obj_lines, name, body, &mut in_ir_file, &mut out_ir_file).map_err(|error| {
            eprintln!("Error during translating, see below");
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
                    if let Err(error) = process_fun(name, range) {
                        eprintln!("Error processing function in {}, {}:\n\t{}", in_src_path.display(), name, error);
                    }
                }
            }
            DoRecurse(false)
        }
        Data::Other => DoRecurse(true)
    });

    // Cleanup: remove objdump assembly file and clang --ast-dump source file
    std::fs::remove_file(&out_full_assembly_temp)?;
    std::fs::remove_file(&out_c_ast_temp)?;

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
    if !status.success() {
        return Err(std::io::Error::new(std::io::ErrorKind::Other, "clang -ast-dump failed"));
    }
    Ok(())
}

lazy_static! {
    static ref ASM_FN_DEF_REGEX: Regex = Regex::new(r"^[0-9]+ <(.+)>:$").expect("internal error: bad regex format?");
}

fn _process_fun(in_obj_lines: &[&str], fn_name: &str, fn_body: &str, in_ir_file: &mut File, out_ir_file: &mut File) -> std::io::Result<()> {
    writeln!(out_ir_file, "{}", fn_body)?;

    let asm_lines = in_obj_lines.iter()
        // From "0000000000000230 <name>:"
        .skip_while(|line| ASM_FN_DEF_REGEX.captures(line).map_or(false, |m| &m[1] == fn_name))
        // To empty line
        .take_while(|line| !line.is_empty());
    for line in asm_lines {
        writeln!(in_ir_file, "{}", line)?;
    }

    Ok(())
}