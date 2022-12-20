import os
import sys
from pathlib import Path
import re
from typing import Iterator, Tuple

from clang.cindex import TranslationUnit, Cursor, SourceRange, Config

from python.code_type import CodeType, ModelStr
from python.log import log
from python.utils import chunk2


class _CCodeType(CodeType):
    def __init__(self, source_extensions, disassembled_extensions):
        super().__init__(source_extensions, [".o"], disassembled_extensions)

    def source_extension_for(self, bytecode_or_disassembled_path: Path) -> str:
        return self.source_extensions[0]

    def process_training(self, input_path: Path, expected_path: Path) -> Iterator[Tuple[ModelStr, ModelStr]]:
        self._assert_disassembled_suffix(input_path)
        self._assert_source_suffix(expected_path)
        if input_path.stat().st_size == 0:
            # Some files are empty (file existence tells Ghidra to ignore, but there is nothing extractable)
            log.debug(f"Skipping empty file {input_path}")
            return
        with input_path.open(encoding="utf8") as input_file:
            expected_source = self._parse_source(expected_path)
            input_data = input_file.read()
            # Functions in disassembled code are already denoted
            input_components = re.split(r"^// FUNCTION (\w+)$", input_data, flags=re.MULTILINE)
            if len(input_components) < 2:
                # File has no functions
                raise Exception("Bad input data format: " + "\n\n".join(input_components))
            for function_name, function_data in chunk2(input_components[1:]):
                expected_function = self._search_function(expected_source.cursor, function_name)
                if expected_function is None:
                    log.debug(
                        f"Failed to find disassembled function {function_name} in expected output "
                        f"{str(expected_path)}"
                    )
                    continue
                expected_function_data = self._node_text(expected_function)
                yield ModelStr(function_data), ModelStr(expected_function_data)

    def process_input(self, input_path: Path) -> Iterator[ModelStr]:
        self._assert_disassembled_suffix(input_path)
        input_source = self._parse_source(input_path)
        for node in input_source.cursor.get_children():
            if node.is_definition():
                yield ModelStr(self._node_text(node))

    def process_output(self, output_data: Iterator[ModelStr]) -> str | bytes:
        return "\n\n".join(output_data)

    def _parse_source(self, source_path: Path) -> TranslationUnit:
        self._assert_source_suffix(source_path)
        unit = TranslationUnit.from_source(
            source_path,
            options=TranslationUnit.PARSE_INCOMPLETE | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )

        # If we have bad imports we need to remove them
        # Unfortunately it doesn't seem like there's an easy better way in Python,
        # because the way to prevent this is Preprocessor::SetSuppressIncludeNotFoundError
        # but it's in a completely different API than python's libclang uses
        # so we would need to rewrite the parsing bindings
        if len(unit.diagnostics) > 0 and unit.diagnostics[0].spelling.endswith("file not found"):
            with source_path.open("r") as file:
                original_contents = file.read()
            modified_path = source_path.with_stem(".tmp" + source_path.stem)
            lines = original_contents.splitlines()
            try:
                while len(unit.diagnostics) > 0 and unit.diagnostics[0].spelling.endswith("file not found"):
                    lines.pop(unit.diagnostics[0].location.line - 1)
                    unit = TranslationUnit.from_source(
                        modified_path,
                        unsaved_files=[(modified_path, "\n".join(lines))],
                        options=TranslationUnit.PARSE_NONE
                    )
            except Exception as e:
                raise Exception("Error parsing after removing bad imports") from e
        return unit

    # noinspection PyMethodMayBeStatic
    def _search_function(self, node: Cursor, function_name: str) -> Cursor | None:
        # Remember: we skip parsing function bodies, so aren't traversing unnecessarily deep
        for node in node.walk_preorder():
            if node.is_definition() and node.mangled_name == function_name:
                return node
        return None

    # noinspection PyMethodMayBeStatic
    def _node_text(self, node: Cursor) -> str:
        extent: SourceRange = node.extent
        with extent.start.file.open() as file:
            file.seek(extent.start.offset)
            return file.read(extent.end.offset - extent.start.offset)

    def _assert_source_suffix(self, input_path: Path):
        if not any(input_path.name.endswith(src_ext) for src_ext in self.source_extensions):
            raise ValueError(f"Expected source suffix, got {input_path.suffix}")

    def _assert_disassembled_suffix(self, disassembled_path: Path):
        if not any(disassembled_path.name.endswith(dis_ext) for dis_ext in self.disassembled_extensions):
            raise ValueError(
                f"Expected disassembled suffix, got {disassembled_path.suffix} (TODO: decompile bytecode using Ghidra "
                f"so that we also accept)"
            )


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
