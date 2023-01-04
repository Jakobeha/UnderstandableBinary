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
        self.decompiled_functions = {}
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

    def add_decompiled(self, path: Path) -> int:
        if path.stat().st_size == 0:
            # Some files are empty (file existence tells Ghidra to ignore, but there is nothing extractable)
            log.debug(f"Skipping empty file {path}")
            return 0
        with path.open("rb") as decompiled_file:
            # We don't want to fail on non-utf8 files (which do exist in the data for some reason)
            decompiled_text = decompiled_file.read().decode("utf-8", errors="ignore")
        # Functions in decompiled code are already denoted
        decompiled_components = re.split(r"^// FUNCTION (.+)$", decompiled_text, flags=re.MULTILINE)
        if len(decompiled_components) % 2 != 1:
            log.warning(f"Bad decompiled data format in {path} ({len(decompiled_components)} components):\n" +
                        "\n---\n".join(decompiled_components))
            return 0
        num_examples_added = 0
        for function_name, function_text in chunk2(decompiled_components[1:]):
            _, function_text, _ = _split_function(function_text)
            function_id = self._get_function_id(path, function_name)
            if function_id not in self.decompiled_functions:
                num_examples_added += 1
            self.decompiled_functions[function_id] = function_text
        return num_examples_added

    def build_examples(self) -> Iterator[tuple[str, ModelStr, ModelStr]]:
        missing_sources = set()
        missing_decompileds = set()
        for function_id, decompiled_function in self.decompiled_functions.items():
            if function_id not in self.source_functions:
                missing_sources.add(function_id)
                continue
            source_function = self.source_functions.pop(function_id)
            yield function_id, ModelStr(source_function), ModelStr(decompiled_function)
        for function_id, source_function in self.source_functions.items():
            missing_decompileds.add(function_id)
        if len(missing_sources) > 0:
            log.debug(f"Missing sources for {len(missing_sources)} decompiled functions:\n\t" +
                      (" ".join(islice(missing_sources, 100)) + "..." if len(missing_sources) > 100
                       else " ".join(missing_sources)))
        if len(missing_decompileds) > 0:
            log.debug(f"Missing decompileds for {len(missing_decompileds)} source functions:\n\t" +
                      (" ".join(islice(missing_decompileds, 100)) + "..." if len(missing_decompileds) > 100
                       else " ".join(missing_decompileds)))

    @staticmethod
    def _get_function_id(path: Path, function_name: str) -> str:
        # Unlike the real stem we don't want *any* extensions
        super_stem = path.name.split(".")[0]
        function_name = function_name.split("<")[0]
        return f"{super_stem}::{function_name}"


class _CCodeType(CodeType, ABC):
    def __init__(self, language: Language, source_extensions, decompiled_extensions):
        super().__init__(source_extensions, [".o"], decompiled_extensions)
        self.language = language
        self.parser = Parser()

    def source_extension_for(self, bytecode_or_decompiled_path: Path) -> str:
        return self.source_extensions[0]

    def ExampleDb(self) -> ExampleDb:
        return _CExampleDb(self.language, self.parser)

    def process_source(self, source_data: Iterator[TransformStr]) -> str | bytes:
        return "\n\n".join(source_text.string for source_text in source_data)

    def process_decompiled(self, decompiled_path: Path) -> Iterator[TransformStr]:
        self._assert_decompiled_suffix(decompiled_path)
        # TODO: Do this properly - walk through *every* node using Cursor, but TransformStr.regular iff the node matches
        #   the query and body has "{" and TransformStr.pass_through otherwise
        decompiled_functions = _scrape_functions(decompiled_path, self.language, self.parser)
        for function in decompiled_functions:
            if '{' in function.text:
                head, body, tail = _split_function(function.text)
                yield TransformStr.pass_through(head)
                yield TransformStr.regular(body)
                yield TransformStr.pass_through(tail)
            else:
                yield TransformStr.pass_through(function.text)

    def _assert_source_suffix(self, decompiled_path: Path):
        if not any(decompiled_path.name.endswith(src_ext) for src_ext in self.source_extensions):
            raise ValueError(f"Expected source suffix, got {decompiled_path.suffix}")

    def _assert_decompiled_suffix(self, decompiled_path: Path):
        if not any(decompiled_path.name.endswith(dis_ext) for dis_ext in self.decompiled_extensions):
            raise ValueError(
                f"Expected decompiled suffix, got {decompiled_path.suffix} (TODO: decompile bytecode using Ghidra "
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
