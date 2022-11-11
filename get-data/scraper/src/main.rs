use std::env::args;
use std::ffi::OsStr;
use rayon::iter::{ParallelBridge, ParallelIterator};
use walkdir::WalkDir;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

fn main() {
    let in_dir = PathBuf::from(args().nth(1).expect("Missing input directory"));
    let out_dir = PathBuf::from(args().nth(2).expect("Missing output directory"));
    let num_processed = AtomicUsize::new(0);
    let iter = WalkDir::new(&in_dir)
        // No need to follow symlinks
        .follow_links(false)
        .into_iter()
        // Multi-threaded
        .par_bridge()
        // Silently skip directories that we can't read
        .filter_map(|e| e.ok())
        // Only look at source or binary files
        .filter(|e| e.path().extension() == Some(OsStr::new("o")) && e.path().with_extension(OsStr::new("c")).exists());
    iter.for_each(|entry| {
        let in_obj_path = entry.into_path();
        let in_src_path = in_obj_path.with_extension("c");
        let subpath = in_obj_path.strip_prefix(&in_dir).expect("input dir entry outside of input, security vulnerability");
        let out_obj_path = out_dir.join(subpath);
        let out_src_path = out_obj_path.with_extension("c");
        // Copy in_path to out_path, silently fail but don't copy only one
        let _ = copy_file(&in_obj_path, &out_obj_path);
        if let Err(_) = copy_file(&in_src_path, &out_src_path) {
            let _ = std::fs::remove_file(&out_obj_path);
        }
        num_processed.fetch_add(1, Ordering::SeqCst);
    });
    println!("Processed {} files!", num_processed.load(Ordering::Acquire));
}

fn copy_file(in_path: &Path, out_path: &Path) -> std::io::Result<()> {
    if let Some(out_parent) = out_path.parent() {
        std::fs::create_dir_all(out_parent)?;
    }
    std::fs::copy(in_path, out_path)?;
    Ok(())
}
