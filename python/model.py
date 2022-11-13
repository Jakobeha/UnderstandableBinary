import os
from typing import Optional

from transformers import AutoTokenizer, T5ForConditionalGeneration, TrainingArguments, Trainer
from pathlib import Path
from log import log
import torch
import evaluate
import shutil
import gc
import numpy as np

from python.code_type import CodeType

USE_SMALL = True


def get_pretrained_id() -> str:
    if USE_SMALL:
        return "Salesforce/codet5-small"
    else:
        return "Salesforce/codet5-large"


def get_default_model():
    return T5ForConditionalGeneration.from_pretrained(get_pretrained_id())


def get_tokenizer():
    return AutoTokenizer.from_pretrained(get_pretrained_id())


def tokenize(tokenizer, data):
    return tokenizer(data, truncation=False, padding="longest", return_tensors="pt")


def tokenize_encode(tokenizer, code):
    return tokenizer.encode(code, truncation=False, padding="longest", return_tensors="pt")


def tokenize_decode(tokenizer, code):
    return tokenizer.decode(code, max_new_tokens=512, skip_special_tokens=True)


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

    def add_dir(self, dir: Path):
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
        _add_item(dir)

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
    def __init__(self, data: ModelData, tokenizer=get_tokenizer()):
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


def get_real_model_dir(model_dir: Path) -> Path:
    checkpoint_paths = [checkpoint_path for checkpoint_path in model_dir.glob("checkpoint_path*")]
    if len(checkpoint_paths) == 0:
        return model_dir
    else:
        # return highest checkpoint
        checkpoint_paths.sort()
        return checkpoint_paths[-1]


def get_model(model_dir: Optional[Path]):
    if model_dir is None or not any(os.scandir(model_dir)):
        return get_default_model()
    else:
        return T5ForConditionalGeneration.from_pretrained(get_real_model_dir(model_dir))
