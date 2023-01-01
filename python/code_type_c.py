import traceback
from abc import ABC
from itertools import islice
from pathlib import Path
import re
from typing import Iterator, Iterable

from tree_sitter import Parser, Language
from tree_sitter_langs import scrape_functions, C_LANGUAGE, CPP_LANGUAGE, TreeSitterFunction

from code_type import CodeType, ModelStr, ExampleDb, TransformStr
from log import log
from utils import chunk2


class _CExampleDb(ExampleDb):
    def __init__(self, language: Language, parser: Parser):
        self.source_functions = {}
        self.disassembled_functions = {}
        self.language = language
        self.parser = parser

    def add_source(self, path: Path) -> int:
        num_examples_added = 0
        try:
            functions = _scrape_functions(path, self.language, self.parser)
            for function in functions:
                if '{' in function.text:
                    _, function_text, _ = _split_function(function.text)
                    function_id = self._get_function_id(path, function.name)
                    if function_id not in self.source_functions:
                        num_examples_added += 1
                    self.source_functions[function_id] = function_text
            if num_examples_added == 0:
                log.debug(f"No functions found in source file {path}")
        except Exception as e:
            traceback.print_exc()
            log.warning(f"Failed to parse {path}: {e}")
        finally:
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
        num_examples_added = 0
        for function_name, function_text in chunk2(disassembled_components[1:]):
            _, function_text, _ = _split_function(function_text)
            function_id = self._get_function_id(path, function_name)
            if function_id not in self.disassembled_functions:
                num_examples_added += 1
            self.disassembled_functions[function_id] = function_text
        return num_examples_added

    def build_examples(self) -> Iterator[tuple[ModelStr, ModelStr]]:
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
            log.debug(f"Missing sources for {len(missing_sources)} disassembled functions:\n\t" +
                      (" ".join(islice(missing_sources, 100)) + "..." if len(missing_sources) > 100
                       else " ".join(missing_sources)))
        if len(missing_disassembleds) > 0:
            log.debug(f"Missing disassembleds for {len(missing_disassembleds)} source functions:\n\t" +
                      (" ".join(islice(missing_disassembleds, 100)) + "..." if len(missing_disassembleds) > 100
                       else " ".join(missing_disassembleds)))

    @staticmethod
    def _get_function_id(path: Path, function_name: str) -> str:
        # Unlike the real stem we don't want *any* extensions
        super_stem = path.name.split(".")[0]
        function_name = function_name.split("<")[0]
        return f"{super_stem}::{function_name}"


class _CCodeType(CodeType, ABC):
    def __init__(self, language: Language, source_extensions, disassembled_extensions):
        super().__init__(source_extensions, [".o"], disassembled_extensions)
        self.language = language
        self.parser = Parser()

    def source_extension_for(self, bytecode_or_disassembled_path: Path) -> str:
        return self.source_extensions[0]

    def ExampleDb(self) -> ExampleDb:
        return _CExampleDb(self.language, self.parser)

    def process_source(self, source_data: Iterator[TransformStr]) -> str | bytes:
        return "\n\n".join(source_text.string for source_text in source_data)

    def process_disassembled(self, disassembled_path: Path) -> Iterator[TransformStr]:
        self._assert_disassembled_suffix(disassembled_path)
        # TODO: Do this properly - walk through *every* node using Cursor, but TransformStr.regular iff the node matches
        #   the query and body has "{" and TransformStr.pass_through otherwise
        disassembled_functions = _scrape_functions(disassembled_path, self.language, self.parser)
        for function in disassembled_functions:
            if '{' in function.text:
                head, body, tail = _split_function(function.text)
                yield TransformStr.pass_through(head)
                yield TransformStr.regular(body)
                yield TransformStr.pass_through(tail)
            else:
                yield TransformStr.pass_through(function.text)

    def _assert_source_suffix(self, disassembled_path: Path):
        if not any(disassembled_path.name.endswith(src_ext) for src_ext in self.source_extensions):
            raise ValueError(f"Expected source suffix, got {disassembled_path.suffix}")

    def _assert_disassembled_suffix(self, disassembled_path: Path):
        if not any(disassembled_path.name.endswith(dis_ext) for dis_ext in self.disassembled_extensions):
            raise ValueError(
                f"Expected disassembled suffix, got {disassembled_path.suffix} (TODO: decompile bytecode using Ghidra "
                f"so that we also accept)"
            )


def _scrape_functions(path: Path, language: Language, parser: Parser) -> Iterable[TreeSitterFunction]:
    return scrape_functions(path, language if path.suffix != "c" else C_LANGUAGE, parser)


def _split_function(node_text: str) -> tuple[str, str, str]:
    head, body_foot = node_text.split("{", 1)
    if '}' in body_foot:
        body, foot = body_foot.rsplit("}", 1)
        return head + "{", body, "}" + foot
    else:
        return head + "{", body_foot, ""


class CCodeType(_CCodeType):
    def __init__(self):
        super().__init__(C_LANGUAGE, [".c"], [".o.c"])

    def __str__(self):
        return "C"

    def __reduce__(self):
        return CCodeType, ()


class CppCodeType(_CCodeType):
    def __init__(self):
        super().__init__(
            CPP_LANGUAGE,
            [".c", ".cpp", ".cc", ".cxx", ".c++"],
            [".o.c", ".o.cpp", ".o.cc", ".o.cxx", ".o.c++"]
        )

    def __str__(self):
        return "C/C++"

    def __reduce__(self):
        return CppCodeType, ()
