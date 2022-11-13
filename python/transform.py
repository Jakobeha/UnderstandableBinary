from pathlib import Path

from tokenizers import Tokenizer

from python.code_type import CodeType
from python.transform_gen import gen_transform
from python.transform_ir import transform_ir_code


def transform_code(tokenizer: Tokenizer, code_type: CodeType, model, src_suffix: str, code: str) -> str:
    # TODO more than transform IR - transform code from bytecode to input IR, and then to output IR
    #   Also if code_type is C and suffix is .o do objdump first
    return transform_ir_code(tokenizer, code_type, model, src_suffix, code)


def transform(
        indir: Path,
        outdir: Path,
        model_dir: Path,
        lang: str,
        count: int,
        force: bool):
    gen_transform(transform_code, indir, outdir, model_dir, lang, count, force)
