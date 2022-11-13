import os
from typing import Optional

from transformers import AutoTokenizer, T5ForConditionalGeneration
from pathlib import Path

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
