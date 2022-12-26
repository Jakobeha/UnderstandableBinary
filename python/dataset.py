import pickle
from pathlib import Path
from typing import BinaryIO, Dict

from code_type import CodeType, ExampleDb
from log import log, logging_progress_bar
from model import tokenize
from tokenizers import Tokenizer

import torch

from utils import walk_files


class ModelData:
    def add_artifact(self, code_types: list[CodeType], root_dir: Path):
        """adds an artifact (self-contained directory of source and disassembled files)"""
        if not root_dir.exists():
            raise ValueError(f"artifact dir {root_dir} does not exist")

        log.info(f"calculating size of artifact {str(root_dir)}")
        num_source_files = 0
        num_disassembled_files = 0
        for file in walk_files(root_dir):
            for code_type in code_types:
                if any(file.name.endswith(extension) for extension in code_type.disassembled_extensions):
                    num_disassembled_files += 1
                elif any(file.name.endswith(extension) for extension in code_type.source_extensions):
                    num_source_files += 1

        dbs: Dict[CodeType, ExampleDb] = {code_type: code_type.ExampleDb() for code_type in code_types}
        num_processed_source_examples = 0
        num_processed_disassembled_examples = 0

        log.info(f"adding artifact {str(root_dir)}")
        # descriptions have trailing spaces to align the progress bars
        with logging_progress_bar(desc="source-files         ", total=num_source_files, position=0,
                                  leave=False) as source_files_pbar:
            with logging_progress_bar(desc="disassembled-files   ", total=num_disassembled_files, position=1,
                                      leave=False) as disassembled_files_pbar:
                with logging_progress_bar(desc="source-examples      ", total=self.max_len, position=2,
                                          leave=False) as source_examples_pbar:
                    with logging_progress_bar(desc="disassembled-examples", total=self.max_len, position=3,
                                              leave=False) as disassembled_examples_pbar:
                        for file in walk_files(root_dir):
                            if 0 < self.max_len <= min(
                                    num_processed_disassembled_examples,
                                    num_processed_disassembled_examples):
                                log.info("** max_len reached, not adding any more examples")
                                break
                            for code_type in code_types:
                                if not (0 < self.max_len <= num_processed_source_examples) and \
                                        any(file.name.endswith(e) for e in code_type.source_extensions) and \
                                        not any(file.name.endswith(e) for e in code_type.disassembled_extensions):
                                    new_source_examples = dbs[code_type].add_source(file)
                                    num_processed_source_examples += new_source_examples
                                    source_files_pbar.update(1)
                                    source_examples_pbar.update(new_source_examples)
                                if not (0 < self.max_len <= num_processed_disassembled_examples) and \
                                        any(file.name.endswith(e) for e in code_type.disassembled_extensions):
                                    new_disassembled_examples = dbs[code_type].add_disassembled(file)
                                    num_processed_disassembled_examples += new_disassembled_examples
                                    disassembled_files_pbar.update(1)
                                    disassembled_examples_pbar.update(new_disassembled_examples)

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
        i = 0
        while i < len(self):
            if self.source_disassembled_code_types[i] not in code_types:
                self.source_disassembled_code_types.pop(i)
                self.sources.pop(i)
                self.disassembleds.pop(i)
            else:
                i += 1

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
