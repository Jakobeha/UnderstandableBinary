from pathlib import Path

from python.code_type import CodeType
from python.log import log
from python.model import tokenize
from tokenizers import Tokenizer

import torch


class ModelData:
    def add_example(self, source_path: Path, bytecode_path: Path):
        if 0 < self.max_len <= len(self):
            return
        with source_path.open(encoding="utf8") as source:
            with bytecode_path.open(encoding="utf8") as bytecode:
                source_text = source.read()
                bytecode_text = bytecode.read()
                # need to read before appending in case there isn't an exception, so that these are aligned
                self.paths.append(source_path)
                self.sources.append(source_text)
                self.bytecodes.append(bytecode_text)

    def add_dir(self, root_dir: Path):
        def _add_item(path: Path):
            if 0 < self.max_len <= len(self):
                return
            if path.is_dir():
                for child_path in path.rglob("*"):
                    _add_item(child_path)
            elif path.suffix == self.code_type.source_extension:
                bytecode_path = path.with_suffix(self.code_type.bytecode_extension)
                if bytecode_path.exists():
                    try:
                        self.add_example(path, bytecode_path)
                        log.info(f"Added {str(path)}")
                    except Exception as e:
                        log.error(f"Failed to add {str(path)}: {e}")
                else:
                    log.warning(f"In-IR file {str(path)} exists but its corresponding out-IR does not")
            else:
                log.debug(f"Ignored {str(path)}")
        _add_item(root_dir)

    def split_off_end(self, interval: float):
        split_index = int(len(self.sources) * interval)
        rhs = ModelData(self.code_type)
        rhs.paths = self.paths[split_index:]
        rhs.sources = self.sources[split_index:]
        rhs.bytecodes = self.bytecodes[split_index:]
        self.paths = self.paths[:split_index]
        self.sources = self.sources[:split_index]
        self.bytecodes = self.bytecodes[:split_index]
        return rhs

    def __len__(self):
        return len(self.paths)

    def __init__(self, code_type: CodeType, max_len: int = 0):
        self.code_type = code_type
        self.max_len = max_len
        self.paths = []
        self.sources = []
        self.bytecodes = []
        self.bytecodes = []


# (idk why but IntelliJ can't find torch.utils.data)
# noinspection PyUnresolvedReferences
class ModelDataset(torch.utils.data.Dataset):
    def __init__(self, data: ModelData, tokenizer: Tokenizer):
        if len(data) == 0:
            raise ValueError("Cannot create dataset from no data")
        self.encodings = tokenize(tokenizer, data.bytecodes)
        self.labels = tokenize(tokenizer, data.sources)

    def __len__(self):
        return len(self.labels.input_ids)

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels.input_ids[idx])
        return item
