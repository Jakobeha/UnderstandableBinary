from pathlib import Path
from tokenizers import Tokenizer

from code_type import CodeType
from transform_gen import gen_transform
from transform_ir import transform_ir_code


def transform_code(tokenizer: Tokenizer, code_type: CodeType, model, src: Path) -> str | bytes:
    model_inputs = code_type.process_input(src)
    model_outputs = (transform_ir_code(tokenizer, model, model_input) for model_input in model_inputs)
    return code_type.process_output(model_outputs)


def transform(
        indir: Path,
        outdir: Path,
        model_dir: Path,
        langs: str,
        count: int,
        force: bool):
    gen_transform(transform_code, indir, outdir, model_dir, langs, count, force)
