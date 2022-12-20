from pathlib import Path

from code_type import CodeType
from log import log
from model import tokenize
from tokenizers import Tokenizer

import torch


class ModelData:
    def add_example(self, code_type: CodeType, source_path: Path, disassembled_path: Path):
        if 0 < self.max_len <= len(self):
            return
        # need to read before appending in case there isn't an exception, so that these are aligned
        examples = code_type.process_training(disassembled_path, source_path)
        num_added = 0
        for source_example, disassembled_example in examples:
            self.paths.append(source_path)
            self.sources.append(source_example)
            self.disassembleds.append(disassembled_example)
            num_added += 1
        log.info(f"Added {num_added} examples from {str(source_path)}")

    def add_dir(self, root_dir: Path):
        def _add_item(path: Path):
            if 0 < self.max_len <= len(self):
                return
            if path.is_dir():
                for child_path in path.rglob("*"):
                    _add_item(child_path)
                return
            for code_type in self.code_types:
                if any(path.name.endswith(src_ext) for src_ext in code_type.source_extensions) and \
                        not any(path.name.endswith(dst_ext) for dst_ext in code_type.disassembled_extensions):
                    base_path_name = next(path.name[:-len(src_ext)]
                                          for src_ext in code_type.source_extensions
                                          if path.name.endswith(src_ext))
                    disassembled_paths = (
                        path.with_name(base_path_name + dst_ext)
                        for dst_ext in code_type.disassembled_extensions
                    )
                    for disassembled_path in disassembled_paths:
                        if disassembled_path.exists():
                            try:
                                self.add_example(code_type, path, disassembled_path)
                            except Exception as e:
                                log.error(f"Failed to add {str(path)}: {e}")
                            return
                    else:
                        log.debug(f"In-IR file {str(path)} exists but its corresponding out-IR does not")
            # Fallback
            log.debug(f"Ignored {str(path)}")

        _add_item(root_dir)

    def split_off_end(self, interval: float):
        split_index = int(len(self.sources) * interval)
        rhs = ModelData(self.code_types)
        rhs.paths = self.paths[split_index:]
        rhs.sources = self.sources[split_index:]
        rhs.disassembleds = self.disassembleds[split_index:]
        self.paths = self.paths[:split_index]
        self.sources = self.sources[:split_index]
        self.disassembleds = self.disassembleds[:split_index]
        return rhs

    def __len__(self):
        return len(self.paths)

    def __init__(self, code_types: list[CodeType], max_len: int = 0):
        self.code_types = code_types
        self.max_len = max_len
        self.paths = []
        self.sources = []
        self.disassembleds = []


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
