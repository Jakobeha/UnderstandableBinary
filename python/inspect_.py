"""Cannot be named inspect because it causes an import error, what? :("""
from pathlib import Path

from code_types import CODE_TYPES
from dataset import ModelData


def inspect(examples_path: Path, langs: str, count: int, skip: int, shuffle_seed: int):
    code_types = [CODE_TYPES[lang] for lang in langs.split(",")]
    data = ModelData.load(examples_path)
    if shuffle_seed != 0:
        data.shuffle(shuffle_seed)
    data.limit_code_types(code_types)
    data.limit_count(count, skip)
    data.print()
