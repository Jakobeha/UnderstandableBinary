import os
import sys
from pathlib import Path
import re
from typing import Iterator, Tuple

from clang.cindex import TranslationUnit, Cursor, SourceRange, Config

from code_type import CodeType, ModelStr, ExampleDb
from log import log
from utils import chunk2


class _CExampleDb(ExampleDb):
    def __init__(self):
        self.source_functions = {}
        self.disassembled_functions = {}

    def add_source(self, path: Path):
        try:
            source_text, source = _parse_source(path)
            for node in source.cursor.walk_preorder():
                if node.is_definition():
                    function_id = self._get_function_id(path, node.spelling)
                    self.source_functions[function_id] = _node_text(path, source_text, node)
        except Exception as e:
            log.warning(f"Failed to parse {path}: {e}")

    def add_disassembled(self, path: Path):
        if path.stat().st_size == 0:
            # Some files are empty (file existence tells Ghidra to ignore, but there is nothing extractable)
            log.debug(f"Skipping empty file {path}")
            return
        with path.open("r") as disassembled_file:
            disassembled_text = disassembled_file.read()
        # Functions in disassembled code are already denoted
        disassembled_components = re.split(r"^// FUNCTION (\w+)$", disassembled_text, flags=re.MULTILINE)
        if len(disassembled_components) < 2:
            # File has no functions
            raise Exception("Bad disassembled data format: " + "\n\n".join(disassembled_components))
        for function_name, function_data in chunk2(disassembled_components[1:]):
            function_id = self._get_function_id(path, function_name)
            self.disassembled_functions[function_id] = function_data

    def build(self) -> Iterator[Tuple[ModelStr, ModelStr]]:
        examples = []
        for function_id, dissassembled_function in self.disassembled_functions:
            if function_id not in self.source_functions:
                log.warning(f"Missing source for {function_id}")
                continue
            source_function = self.source_functions[function_id]
            examples.append((ModelStr(source_function), ModelStr(dissassembled_function)))
        return examples

    @staticmethod
    def _get_function_id(path: Path, function_name: str) -> str:
        return f"{path.name}::{function_name}"


class _CCodeType(CodeType):
    def __init__(self, source_extensions, disassembled_extensions):
        super().__init__(source_extensions, [".o"], disassembled_extensions)

    def source_extension_for(self, bytecode_or_disassembled_path: Path) -> str:
        return self.source_extensions[0]

    def ExampleDb(self) -> ExampleDb:
        return _CExampleDb()

    def process_source(self, source_data: Iterator[ModelStr]) -> str | bytes:
        return "\n\n".join(source_data)

    def process_disassembled(self, disassembled_path: Path) -> Iterator[ModelStr]:
        self._assert_disassembled_suffix(disassembled_path)
        disassembled_text, disassembled_source = _parse_source(disassembled_path)
        for node in disassembled_source.cursor.get_children():
            if node.is_definition():
                yield ModelStr(_node_text(disassembled_path, disassembled_text, node))

    def _assert_source_suffix(self, disassembled_path: Path):
        if not any(disassembled_path.name.endswith(src_ext) for src_ext in self.source_extensions):
            raise ValueError(f"Expected source suffix, got {disassembled_path.suffix}")

    def _assert_disassembled_suffix(self, disassembled_path: Path):
        if not any(disassembled_path.name.endswith(dis_ext) for dis_ext in self.disassembled_extensions):
            raise ValueError(
                f"Expected disassembled suffix, got {disassembled_path.suffix} (TODO: decompile bytecode using Ghidra "
                f"so that we also accept)"
            )


def _parse_source(source_path: Path) -> (str, TranslationUnit):
    with source_path.open("r") as file:
        text = file.read()
    unit = TranslationUnit.from_source(
        source_path,
        unsaved_files=[(source_path, text)],
        options=TranslationUnit.PARSE_INCOMPLETE | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
    )

    # If the entire code is wrapped in #ifdef or #if, we will remove it
    if next(unit.cursor.get_children(), None) is None:
        lines = text.splitlines()
        try:
            while lines[-1].strip() == "":
                lines.pop()
            if lines[-1].startswith("#endif"):
                ifdef_idx = next(
                    (i for i, line in enumerate(lines) if line.startswith("#ifdef ") or line.startswith("#if ")),
                    None
                )
                if ifdef_idx is not None:
                    lines.pop()
                    lines.pop(ifdef_idx)
            text = "\n".join(lines)
            unit = TranslationUnit.from_source(
                source_path,
                unsaved_files=[(source_path, text)],
                options=TranslationUnit.PARSE_NONE
            )
        except Exception as e:
            raise Exception("Error parsing after removing surrounding #ifdef bad imports") from e
    return text, unit


# noinspection PyMethodMayBeStatic
def _node_text(source_path: Path, text: str, node: Cursor) -> str:
    extent: SourceRange = node.extent
    path = extent.start.file.name
    if path != str(source_path):
        with os.open(path, os.O_RDONLY) as file:
            text = file.read()
    return text[extent.start.offset:extent.end.offset]


class CCodeType(_CCodeType):
    def __init__(self):
        super().__init__([".c", ".h"], [".o.c"])


class CppCodeType(_CCodeType):
    def __init__(self):
        super().__init__([".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp"], [".o.cpp", ".o.cc", ".o.cxx", ".o.c++"])


def configure_clang():
    # On macOS, the default clang installation is not in the path, but is in the CommandLineTools
    if sys.platform == "darwin" and os.path.isfile("/Library/Developer/CommandLineTools/usr/lib/libclang.dylib"):
        Config.set_library_file("/Library/Developer/CommandLineTools/usr/lib/libclang.dylib")


configure_clang()
