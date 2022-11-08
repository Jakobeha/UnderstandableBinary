from pathlib import Path
import shutil
from utils import check_dir, mk_empty_dir


def compile(indir: Path, outdir: Path, lang: str, count: int, force: bool):
    check_dir(indir)
    mk_empty_dir(outdir, force)
    try:
        match lang:
            case "c", "cpp":
                compile_c(indir, outdir, count)
    except Exception as e:
        shutil.rmtree(outdir)
        raise e