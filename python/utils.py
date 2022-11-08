from pathlib import Path
import shutil


def check_dir(path: Path):
    """assert that the path exists and is a directory"""
    if not path.exists():
        raise ValueError(f"Path {path} does not exist")
    if not path.is_dir():
        raise ValueError(f"Path {path} is not a directory")


def mk_empty_dir(path: Path, force: bool):
    """create an empty directory at path. If force, will rm -rf if existing"""
    if path.exists():
        if force:
            shutil.rmtree(path)
        else:
            raise ValueError(f"Path {path} already exists")
    path.mkdir(parents=True)
