from pathlib import Path

from tokenizers import Tokenizer

from code_type import CodeType
from model import tokenize_encode, tokenize_decode
from transform_gen import gen_transform


def transform_raw_ir_code(tokenizer: Tokenizer, _code_type: CodeType, model, src: Path) -> str:
    with src.open(encoding="utf8") as src:
        code = src.read()
    return transform_ir_code(tokenizer, model, code)


def transform_ir_code(tokenizer: Tokenizer, model, code: str) -> str:
    input_ids = tokenize_encode(tokenizer, code)
    outputs = model.generate(input_ids, max_new_tokens=512)
    return tokenize_decode(tokenizer, outputs[0])


def transform_ir(
        indir: Path,
        outdir: Path,
        model_dir: Path,
        langs: str,
        count: int,
        force: bool):
    gen_transform(transform_raw_ir_code, indir, outdir, model_dir, langs, count, force)
