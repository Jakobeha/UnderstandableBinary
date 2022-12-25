import os
import sys
import traceback
from itertools import islice
from pathlib import Path
import re
from typing import Iterator, Tuple, Optional

from clang.cindex import TranslationUnit, Cursor, SourceRange, Config, CursorKind

from code_type import CodeType, ModelStr, ExampleDb, TransformStr
from log import log
from utils import chunk2

# these are monkey-patched but IntelliJ can't see them
# noinspection PyUnresolvedReferences
FUNCTION_KINDS = {
    CursorKind.FUNCTION_DECL,
    CursorKind.CXX_METHOD,
    CursorKind.OBJC_CLASS_METHOD_DECL,
    CursorKind.OBJC_INSTANCE_METHOD_DECL
}


class _CExampleDb(ExampleDb):
    def __init__(self):
        self.source_functions = {}
        self.disassembled_functions = {}

    def add_source(self, path: Path) -> int:
        num_examples_added = 0
        try:
            source_text, source = _parse_source(path)
            for node in source.cursor.walk_preorder():
                if node.kind in FUNCTION_KINDS:
                    node_text = _node_text(path, source_text, node)
                    if node_text is not None:
                        function_id = self._get_function_id(path, node.spelling)
                        self.source_functions[function_id] = node_text
                        num_examples_added += 1
                    else:
                        log.warning(f"Failed to get text for {node.spelling} in {path}")
        except Exception as e:
            traceback.print_exc()
            log.warning(f"Failed to parse {path}: {e}")
        return num_examples_added

    def add_disassembled(self, path: Path) -> int:
        if path.stat().st_size == 0:
            # Some files are empty (file existence tells Ghidra to ignore, but there is nothing extractable)
            log.debug(f"Skipping empty file {path}")
            return 0
        with path.open("rb") as disassembled_file:
            # We don't want to fail on non-utf8 files (which do exist in the data for some reason)
            disassembled_text = disassembled_file.read().decode("utf-8", errors="ignore")
        # Functions in disassembled code are already denoted
        disassembled_components = re.split(r"^// FUNCTION (.+)$", disassembled_text, flags=re.MULTILINE)
        if len(disassembled_components) % 2 != 1:
            log.warning(f"Bad disassembled data format in {path} ({len(disassembled_components)} components):\n" +
                        "\n---\n".join(disassembled_components))
            return 0
        for function_name, function_data in chunk2(disassembled_components[1:]):
            function_id = self._get_function_id(path, function_name)
            self.disassembled_functions[function_id] = function_data
        return (len(disassembled_components) - 1) // 2

    def build_examples(self) -> Iterator[Tuple[ModelStr, ModelStr]]:
        missing_sources = set()
        missing_disassembleds = set()
        for function_id, disassembled_function in self.disassembled_functions.items():
            if function_id not in self.source_functions:
                missing_sources.add(function_id)
                continue
            source_function = self.source_functions.pop(function_id)
            yield ModelStr(source_function), ModelStr(disassembled_function)
        for function_id, source_function in self.source_functions.items():
            missing_disassembleds.add(function_id)
        if len(missing_sources) > 0:
            log.warning(f"Missing sources for {len(missing_sources)} functions:\n\t" +
                        (" ".join(islice(missing_sources, 100)) + "..." if len(missing_sources) > 100
                         else " ".join(missing_sources)))
        if len(missing_disassembleds) > 0:
            log.warning(f"Missing disassembleds for {len(missing_disassembleds)} functions:\n\t" +
                        (" ".join(islice(missing_disassembleds, 100)) + "..." if len(missing_disassembleds) > 100
                         else " ".join(missing_disassembleds)))

    @staticmethod
    def _get_function_id(path: Path, function_name: str) -> str:
        # Unlike the real stem we don't want *any* extensions
        super_stem = path.name.split(".")[0]
        return f"{super_stem}::{function_name}"


class _CCodeType(CodeType):
    def __init__(self, source_extensions, disassembled_extensions):
        super().__init__(source_extensions, [".o"], disassembled_extensions)

    def source_extension_for(self, bytecode_or_disassembled_path: Path) -> str:
        return self.source_extensions[0]

    def ExampleDb(self) -> ExampleDb:
        return _CExampleDb()

    def process_source(self, source_data: Iterator[TransformStr]) -> str | bytes:
        return "\n\n".join(source_text.string for source_text in source_data)

    def process_disassembled(self, disassembled_path: Path) -> Iterator[TransformStr]:
        self._assert_disassembled_suffix(disassembled_path)
        disassembled_text, disassembled_source = _parse_source(disassembled_path)
        for node in disassembled_source.cursor.get_children():
            node_text = _node_text(disassembled_path, disassembled_text, node)
            if node_text is not None:
                if node.kind in FUNCTION_KINDS:
                    yield TransformStr.regular(node_text)
                else:
                    yield TransformStr.pass_through(node_text)

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
    with source_path.open("rb") as file:
        # We don't want to fail on non-utf8 files (which do exist in the data for some reason)
        text = file.read().decode("utf-8", errors="ignore")
    unit = TranslationUnit.from_source(
        source_path,
        unsaved_files=[(source_path, text)],
        options=TranslationUnit.PARSE_INCOMPLETE | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
    )

    # If the entire code is wrapped in #ifdef or #if, we will remove it
    if next(unit.cursor.get_children(), None) is None:
        lines = text.splitlines()
        try:
            while len(lines) > 0 and lines[-1].strip() == "":
                lines.pop()
            if len(lines) == 0:
                # This code path is reached when we have an empty file (or a file with only whitespace)
                return "", unit
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
def _node_text(source_path: Path, text: str, node: Cursor) -> Optional[str]:
    extent: SourceRange = node.extent
    if extent.start.file is None:
        return None
    path = extent.start.file.name
    if path != str(source_path):
        with open(path, "r") as file:
            text = file.read()
    return text[extent.start.offset:extent.end.offset]


class CCodeType(_CCodeType):
    def __init__(self):
        super().__init__([".c", ".h"], [".o.c"])

    def __str__(self):
        return "C"


class CppCodeType(_CCodeType):
    def __init__(self):
        super().__init__([".c", ".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp"], [".o.c", ".o.cpp", ".o.cc", ".o.cxx", ".o.c++"])

    def __str__(self):
        return "C/C++"


def configure_clang():
    # On macOS, the default clang installation is not in the path, but is in the CommandLineTools
    if sys.platform == "darwin" and os.path.isfile("/Library/Developer/CommandLineTools/usr/lib/libclang.dylib"):
        Config.set_library_file("/Library/Developer/CommandLineTools/usr/lib/libclang.dylib")


configure_clang()
