use std::env::args;
use std::ffi::OsStr;
use rayon::iter::ParallelBridge;
use walkdir::{WalkDir, DirEntry};
use std::path::{Path, PathBuf};

const EXTENSIONS: &[&OsStr; 4] = &[
    OsStr::new(".c"),
    OsStr::new(".h"),
    OsStr::new(".hpp"),
    OsStr::new(".o")
];

fn main() {
    let in_dir = PathBuf::from(args().nth(1).expect("Missing input directory"));
    let out_dir = PathBuf::from(args().nth(2).expect("Missing output directory"));
    let iter = WalkDir::new(in_dir)
        // No need to follow symlinks
        .follow_links(false)
        .into_iter()
        // Multi-threaded
        .par_bridge()
        // Silently skip directories that we can't read
        .filter_map(|e| e.ok())
        // Only look at source or binary files
        .filter(|e| e.path().extension().map_or_else(false, EXTENSIONS.contains));
    iter.for_each(|entry: DirEntry| {
        let in_path = entry.into_path();
        let subpath = in_path.strip_prefix(&in_dir).expect("input dir entry outside of input, security vulnerability");
        let out_path = out_dir.join(subpath);
        // Copy in_path to out_path, silently fail
        let _ = copy_file(&in_path, &out_path);
    });
    println!("Hello, world!");
}

fn copy_file(in_path: &Path, out_path: &Path) -> std::io::Result<()> {
    if let Some(out_parent) = out_path.parent() {
        std::fs::create_dir_all(out_parent)?;
    }
    std::fs::copy(in_path, out_path)?;
    Ok(())
}
