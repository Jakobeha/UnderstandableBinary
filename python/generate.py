from pathlib import Path
import subprocess
from utils import check_dir, mk_empty_dir, PROJECT_PATH

PREPROCESSOR_DIR = PROJECT_PATH / "preprocessor"


def generate(indir: Path, outdir: Path, lang: str, count: int, force: bool):
    check_dir(indir)
    mk_empty_dir(outdir, force)
    subprocess.run(
        # Paths must be absolute since we change cwd
        ["cargo", "run", "--release", "--", str(indir.absolute()), str(outdir.absolute()), lang, str(count)],
        cwd=PREPROCESSOR_DIR,
        check=True
    )
