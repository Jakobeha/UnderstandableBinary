from pathlib import Path
import subprocess
from utils import check_dir, mk_empty_dir, PROJECT_PATH

PREPROCESSOR_DIR = PROJECT_PATH / "preprocessor"


def generate(indir: Path, outdir: Path, langs: str, count: int, force: bool):
    raise Exception("TODO: obsolete")