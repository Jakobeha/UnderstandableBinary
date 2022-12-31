from pathlib import Path

from code_types import CODE_TYPES
from dataset import ModelData
from log import log
from utils import mk_empty_binary_file


def generate(dataset_dir: Path, examples_path: Path, langs: str, count: int, force: bool):
    code_types = [CODE_TYPES[lang] for lang in langs.split(",")]
    with mk_empty_binary_file(examples_path, force) as examples_file:
        train_data = ModelData(count)
        try:
            train_data.add_repo(code_types, dataset_dir)
        except KeyboardInterrupt:
            # explicitly don't print traceback on this exception
            log.info("** Interrupted")
        finally:
            train_data.save(examples_file)
