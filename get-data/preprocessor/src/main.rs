mod io_write_to_fmt_write;

use std::env::args;
use std::ffi::OsStr;
use std::fs::File;
use std::io::{Write, stderr};
use rayon::iter::{ParallelBridge, ParallelIterator};
use walkdir::{DirEntry, WalkDir};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use regex::Regex;
use lazy_static::lazy_static;
use io_write_to_fmt_write::{IoWrite2FmtWrite, IoWrite2FmtWriteCatch};

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
    let out_full_assembly_temp = out_dir.join("full.s");
    objdump(in_obj_path, &out_full_assembly_temp)?;

    // Parse C code
    let config = lang_c::driver::Config::default();
    let in_c = lang_c::driver::parse(&config, &in_src_path)
        .map_err(|error| std::io::Error::new(std::io::ErrorKind::Other, error))?;

    // Break assembly into lines, allocate vector to store them
    let in_obj_text = std::fs::read_to_string(in_obj_path)?;
    let in_obj_lines = in_obj_text.lines().collect::<Vec<_>>();

    // Visitor:
    //   For each declaration (training example) in the C code, extract the corresponding assembly
    //   create 2 corresponding files to store both
    struct Visitor<'a> {
        in_src_path: &'a Path,
        in_obj_lines: &'a [&'a str],
        out_dir: &'a Path,
        err_printer: &'a mut lang_c::print::Printer<'a>
    }
    impl<'a> Visitor<'a> {
        fn _visit_function_definition(&mut self, function_definition: &'a lang_c::ast::FunctionDefinition, span: &'a lang_c::span::Span) -> std::io::Result<()> {
            match &function_definition.declarator.node.kind.node {
                lang_c::ast::DeclaratorKind::Identifier(fn_ident) => {
                    let fn_name = &fn_ident.node.name;
                    let fn_path = self.out_dir.join(fn_name);
                    let mut in_ir_file = File::create(fn_path.with_extension("c"))?;
                    let mut out_ir_file = File::create(fn_path.with_extension("s"))?;
                    // Like _process, don't keep one corresponding file without the other
                    _process_fun(&self.in_obj_lines, fn_name, function_definition, span, &mut in_ir_file, &mut out_ir_file).map_err(|error| {
                        eprintln!("Translation error for {}, see below", fn_name);
                        std::fs::remove_file(fn_path.with_extension("c")).expect("Failed to remove input IR file");
                        std::fs::remove_file(fn_path.with_extension("s")).expect("Failed to remove output IR file");
                        error
                    })
                },
                _ => {
                    Err(std::io::Error::new(std::io::ErrorKind::Other, "Unexpected function declarator kind"))
                },
            }
        }
    }
    // Also print errors but don't stop processing, just skip
    impl<'a> lang_c::visit::Visit<'a> for Visitor<'a> {
        fn visit_function_definition(&mut self, function_definition: &'a lang_c::ast::FunctionDefinition, span: &'a lang_c::span::Span) {
            if let Err(error) = self._visit_function_definition(function_definition, span) {
                lang_c::visit::Visit::visit_function_definition(self.err_printer, function_definition, span);
                eprintln!("Error processing function in {}:\n\t{}", self.in_src_path.display(), error);
            }
        }
    }

    // Run the visitor
    lang_c::visit::Visit::visit_translation_unit(
        &mut Visitor {
            in_src_path,
            in_obj_lines: &in_obj_lines,
            out_dir,
            err_printer: &mut lang_c::print::Printer::new(&mut IoWrite2FmtWrite::new(&mut stderr())),
        },
        &in_c.unit
    );

    // Cleanup: remove objdump assembly file
    std::fs::remove_file(&out_full_assembly_temp)?;

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

lazy_static! {
    static ref ASM_FN_DEF_REGEX: Regex = Regex::new(r"^[0-9]+ <(.+)>:$").expect("internal error: bad regex format?");
}

fn _process_fun(in_obj_lines: &[&str], fn_name: &str, fn_def: &lang_c::ast::FunctionDefinition, fn_def_spam: &lang_c::span::Span, in_ir_file: &mut File, out_ir_file: &mut File) -> std::io::Result<()> {
    let mut out_ir_file = IoWrite2FmtWriteCatch::new(out_ir_file);
    let mut printer = lang_c::print::Printer::new(&mut out_ir_file);
    lang_c::visit::Visit::visit_function_definition(&mut printer, fn_def, fn_def_spam);

    let asm_lines = in_obj_lines.iter()
        // From "0000000000000230 <name>:"
        .skip_while(|line| ASM_FN_DEF_REGEX.captures(line).map_or(false, |m| &m[1] == fn_name))
        // To empty line
        .take_while(|line| !line.is_empty());
    for line in asm_lines {
        writeln!(in_ir_file, "{}", line)?;
    }

    out_ir_file.into_result()
}