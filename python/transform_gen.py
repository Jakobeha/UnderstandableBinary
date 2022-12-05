import shutil
from pathlib import Path
from typing import Callable, Any

from tokenizers import Tokenizer

from code_type import CodeType, CODE_TYPES
from log import log
from model import get_tokenizer, get_model
from utils import check_dir, mk_empty_dir


def gen_transform_dir(
        do_transform: Callable[[Tokenizer, CodeType, Any, Path], str],
        tokenizer: Tokenizer,
        code_type: CodeType,
        model: Any,
        count: int,
        src_root: Path,
        dest: Path):
    num_transformed = [0]

    # noinspection PyShadowingNames
    def transform_code_file(src: Path, dest: Path):
        if num_transformed[0] >= count:
            log.info(f"Skipping transforming file {str(src)} as we exceeded count, just copying...")
            shutil.copy(src, dest)
            return
        
        log.info(f"Transforming file {str(src)}")

        with dest.open("w", encoding="utf8") as dest:
            transformed_code = do_transform(tokenizer, code_type, model, src)
            dest.write(transformed_code)
            num_transformed[0] += 1

    # noinspection PyShadowingNames
    def transform_file(src: Path, dest: Path):
        if any(src.name.endswith(bytecode_extension) for bytecode_extension in code_type.bytecode_extensions):
            transform_code_file(src, dest.with_suffix(code_type.source_extension))
        else:
            log.debug(f"Copying non-code file {str(src)}")

            shutil.copy(src, dest)

    # noinspection PyShadowingNames
    def transform_sub_dir(src: Path, dest: Path, exist_ok: bool):
        if src.is_dir():
            if src_root != src:
                log.debug(f"Transforming sub-directory {str(src)}")

            dest.mkdir(exist_ok=exist_ok)
            for child in src.iterdir():
                transform_sub_dir(child, dest.joinpath(child.name), exist_ok=False)
        else:
            transform_file(src, dest)

    transform_sub_dir(src_root, dest, exist_ok=True)


def gen_transform(
        do_transform: Callable[[Tokenizer, CodeType, Any, Path], str],
        indir: Path,
        outdir: Path,
        model_dir: Path,
        lang: str,
        count: int,
        force: bool):
    check_dir(indir)
    mk_empty_dir(outdir, force)

    tokenizer = get_tokenizer()
    code_type = CODE_TYPES[lang]
    model = get_model(model_dir)

    gen_transform_dir(do_transform, tokenizer, code_type, model, count, indir, outdir)
