import shutil
from itertools import chain
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
        code_types: list[CodeType],
        model: Any,
        count: int,
        src_root: Path,
        dest: Path):
    num_transformed = [0]

    # noinspection PyShadowingNames
    def transform_code_file(code_type: CodeType, src: Path, dest: Path):
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
        for code_type in code_types:
            for extension in chain(code_type.bytecode_extensions, code_type.disassembled_extensions):
                if src.name.endswith(extension):
                    dest_name = src.name[:-len(extension)] + code_type.source_extension_for(src)
                    # don't need to pass extension because it's in src
                    transform_code_file(code_type, src, dest.with_name(dest_name))
                    break
        # Fallback
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
        langs: str,
        count: int,
        force: bool):
    check_dir(indir)
    mk_empty_dir(outdir, force)

    tokenizer = get_tokenizer()
    code_types = [CODE_TYPES[lang] for lang in langs.split(",")]
    model = get_model(model_dir)

    gen_transform_dir(do_transform, tokenizer, code_types, model, count, indir, outdir)
