import os
from pathlib import Path
import shutil
from typing import Iterable, TypeVar, BinaryIO, Generic

T = TypeVar('T')

PROJECT_PATH = Path(__file__).parent.parent
DEFAULT_DATASET_PATH = PROJECT_PATH.parent / "UnderstandableBinary-data"
DEFAULT_EXAMPLES_PATH = PROJECT_PATH.parent / "UnderstandableBinary-examples.pickle"
DEFAULT_MODEL_PATH = PROJECT_PATH.parent / "UnderstandableBinary-model"

INT32_MAX = 2_147_483_647  # 2^31 - 1


def path_or_float(arg) -> Path | float:
    """ArgumentParser type for a path or a float"""
    try:
        return float(arg)
    except ValueError:
        return Path(arg)


# noinspection PyShadowingBuiltins
def walk_files(root_dir: Path) -> Iterable[Path]:
    """Walk a directory, yielding paths to all files (including the root)"""
    for dir, _, filenames in os.walk(root_dir):
        for filename in filenames:
            yield Path(dir, filename)


def walk_files_up_to_depth(root_dir: Path, max_depth: int) -> Iterable[Path]:
    """Walk a directory, yielding paths to all files up to a certain depth (including the root; depth 0 = only root)"""
    yield root_dir
    if max_depth == 0 or not root_dir.is_dir():
        return
    for child in root_dir.iterdir():
        yield from walk_files_up_to_depth(child, max_depth - 1)


# From https://stackoverflow.com/questions/2425096/how-to-write-a-generator-that-returns-all-but-last-items-in-the-iterable-in-pyth
def all_but_last(iterable: Iterable[T]) -> Iterable[T]:
    it = iter(iterable)
    current = next(it)
    for i in it:
        yield current
        current = i


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


def mk_empty_binary_file(path: Path, force: bool) -> BinaryIO:
    """create an empty binary file open for writing at path. If force, will rm if existing"""
    if path.exists():
        if force:
            path.unlink()
        else:
            raise ValueError(f"Path {path} already exists")
    return path.open("wb")


def chunk2(iterable: Iterable[T]) -> Iterable[tuple[T, T]]:
    """Chunk an iterable into pairs"""
    it = iter(iterable)
    while True:
        try:
            yield next(it), next(it)
        except StopIteration:
            return


class Reference(Generic[T]):
    def __init__(self, value: T):
        self.value = value
