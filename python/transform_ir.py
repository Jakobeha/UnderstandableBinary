import shutil
from pathlib import Path

from tokenizers import Tokenizer

from python.code_type import CodeType
from python.model import tokenize_encode, tokenize_decode
from python.transform_gen import gen_transform


def transform_ir_code(tokenizer: Tokenizer, _code_type: CodeType, model, src_suffix: str, code: str) -> str:
    input_ids = tokenize_encode(tokenizer, code)
    outputs = model.generate(input_ids)
    return tokenize_decode(tokenizer, outputs[0])


def transform_ir(
        indir: Path,
        outdir: Path,
        model_dir: Path,
        lang: str,
        count: int,
        force: bool):
    gen_transform(transform_ir_code, indir, outdir, model_dir, lang, count, force)
