from pathlib import Path
from tokenizers import Tokenizer

from code_type import CodeType, TransformStr
from transform_gen import gen_transform
from transform_ir import transform_ir_code


def _transform_code1(tokenizer: Tokenizer, model, input: TransformStr) -> TransformStr:
    match input.type:
        case TransformStr.REGULAR:
            return TransformStr.regular(transform_ir_code(tokenizer, model, input.string))
        case TransformStr.PASS_THROUGH:
            return TransformStr.pass_through(input.string)


def transform_code(tokenizer: Tokenizer, code_type: CodeType, model, src: Path) -> str | bytes:
    model_inputs = code_type.process_decompiled(src)
    model_outputs = (_transform_code1(tokenizer, model, model_input) for model_input in model_inputs)
    return code_type.process_source(model_outputs)


def transform(
        indir: Path,
        outdir: Path,
        model_dir: Path,
        langs: str,
        count: int,
        force: bool):
    gen_transform(transform_code, indir, outdir, model_dir, langs, count, force)
