from pathlib import Path
import subprocess

from tokenizers import Tokenizer

from code_type import CodeType, CODE_TYPE_C
from transform_gen import gen_transform
from transform_ir import transform_ir_code


def transform_code(tokenizer: Tokenizer, code_type: CodeType, model, src: Path) -> str:
    if code_type == CODE_TYPE_C:
        # TODO: Do this in Rust, reusing the preprocessor:
        #   Copy the code into a temporary directory with the files properly disassembled, and then run directly on the
        #   IR (might get rid of gen_transform as well)
        match src.suffix:
            case ".o":
                code = subprocess.run(
                    ["objdump", "-drwC", "-Mintel", str(src)],
                    stdout=subprocess.PIPE,
                    check=True
                ).stdout.decode("utf8")
            case ".s":
                with src.open(encoding="utf8") as src:
                    code = src.read()
            case src_suffix:
                raise ValueError(f"Unknown suffix {src_suffix}")
        blocks = code.split("\n\n")
        #
        return "\n\n".join(transform_ir_code(tokenizer, model, block) for block in blocks)
    else:
        raise ValueError(f"Unsupported code type: {code_type}")


def transform(
        indir: Path,
        outdir: Path,
        model_dir: Path,
        lang: str,
        count: int,
        force: bool):
    gen_transform(transform_code, indir, outdir, model_dir, lang, count, force)
