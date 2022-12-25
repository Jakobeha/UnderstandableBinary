import pickle
from pathlib import Path
from typing import BinaryIO, Dict

from code_type import CodeType, ExampleDb
from log import log, logging_progress_bar
from model import tokenize
from tokenizers import Tokenizer

import torch

from utils import Reference


class ModelData:
    def add_artifact(self, code_types: list[CodeType], root_dir: Path):
        if not root_dir.exists():
            raise ValueError(f"artifact dir {root_dir} does not exist")

        """adds an artifact (self-contained directory of source and disassembled files)"""
        dbs: Dict[CodeType, ExampleDb] = {code_type: code_type.ExampleDb() for code_type in code_types}
        total_num_expected_source_examples = Reference(0)
        total_num_expected_disassembled_examples = Reference(0)

        log.info(f"adding artifact {str(root_dir)}")
        with logging_progress_bar(total=self.max_len, position=0, leave=False) as source_pbar:
            with logging_progress_bar(total=self.max_len, position=1, leave=False) as disassembled_pbar:
                def _add_item(path: Path):
                    if 0 < self.max_len <= min(
                            total_num_expected_source_examples.value,
                            total_num_expected_disassembled_examples.value):
                        log.info("** max_len reached, not adding any more examples")
                        return
                    if path.is_dir():
                        for child_path in path.rglob("*"):
                            _add_item(child_path)
                        return
                    for code_type in code_types:
                        if not (0 < self.max_len <= total_num_expected_source_examples.value) and \
                                any(path.name.endswith(src_ext) for src_ext in code_type.source_extensions) and \
                                not any(path.name.endswith(dst_ext) for dst_ext in code_type.disassembled_extensions):
                            new_source_examples = dbs[code_type].add_source(path)
                            source_pbar.update(new_source_examples)
                            total_num_expected_source_examples.value += new_source_examples
                        if not (0 < self.max_len <= total_num_expected_disassembled_examples.value) and \
                                any(path.name.endswith(dst_ext) for dst_ext in code_type.disassembled_extensions):
                            new_disassembled_examples = dbs[code_type].add_disassembled(path)
                            disassembled_pbar.update(new_disassembled_examples)
                            total_num_expected_disassembled_examples.value += new_disassembled_examples
                _add_item(root_dir)

        # Add all examples, but
        # - don't add more than max_len
        # - add examples from each language in a round-robin fashion
        # - print the number of examples we added of each language
        for code_type, db in dbs.items():
            num_examples_added = 0
            for source, disassembled in db.build_examples():
                self.source_disassembled_code_types.append(code_type)
                self.sources.append(source)
                self.disassembleds.append(disassembled)
                num_examples_added += 1
            log.info(f"** {code_type} - {num_examples_added} examples")

    def split_off_end(self, interval: float):
        split_index = int(len(self) * interval)
        rhs = ModelData()
        rhs.source_disassembled_code_types = self.source_disassembled_code_types[split_index:]
        rhs.sources = self.sources[split_index:]
        rhs.disassembleds = self.disassembleds[split_index:]
        self.source_disassembled_code_types = self.source_disassembled_code_types[:split_index]
        self.sources = self.sources[:split_index]
        self.disassembleds = self.disassembleds[:split_index]
        return rhs

    def limit_code_types(self, code_types: list[CodeType]):
        for i in range(len(self)):
            if self.source_disassembled_code_types[i] not in code_types:
                self.source_disassembled_code_types.pop(i)
                self.sources.pop(i)
                self.disassembleds.pop(i)

    def limit_count(self, count: int):
        self.source_disassembled_code_types = self.source_disassembled_code_types[:count]
        self.sources = self.sources[:count]
        self.disassembleds = self.disassembleds[:count]

    def __len__(self):
        return len(self.sources)

    def __init__(self, max_len: int = 0):
        self.max_len = max_len
        self.source_disassembled_code_types = []
        self.sources = []
        self.disassembleds = []

    PICKLE_PROTOCOL = 5

    def save(self, path_or_file: Path | BinaryIO):
        if isinstance(path_or_file, Path):
            with path_or_file.open("wb") as file:
                self.save(file)
        else:
            pickle.dump(self, path_or_file, protocol=self.PICKLE_PROTOCOL)

    @staticmethod
    def load(path: Path):
        with path.open("rb") as file:
            return pickle.load(file)


# (idk why but IntelliJ can't find torch.utils.data)
# noinspection PyUnresolvedReferences
class ModelDataset(torch.utils.data.Dataset):
    def __init__(self, data: ModelData, tokenizer: Tokenizer):
        if len(data) == 0:
            raise ValueError("Cannot create dataset from no data")
        self.encodings = tokenize(tokenizer, data.disassembleds)
        self.labels = tokenize(tokenizer, data.sources)

    def __len__(self):
        return len(self.labels.input_ids)

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels.input_ids[idx])
        return item
