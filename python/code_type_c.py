import os
import sys
import traceback
from abc import ABC
from itertools import islice, chain
from pathlib import Path
import re
from typing import Iterator, Tuple, Optional

from clang.cindex import TranslationUnit, Cursor, SourceRange, Config, CursorKind, Index, File, Diagnostic

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
        self.index = Index.create()

    SOURCE_SIZE_LIMIT = int(os.environ.get("SOURCE_SIZE_LIMIT", 10_000_000))

    def add_source(self, path: Path) -> int:
        num_examples_added = 0
        if self.SOURCE_SIZE_LIMIT != 0 and path.stat().st_size > self.SOURCE_SIZE_LIMIT:
            log.debug(f"Skipping large source file {path}")
            return 0
        try:
            source_text, source = _parse_source(path, self.index)
            for node in source.cursor.walk_preorder():
                if node.kind in FUNCTION_KINDS:
                    node_text = _node_text(path, source_text, node)
                    if node_text is not None:
                        if '{' in node_text:
                            _, node_text, _ = _split_function(node_text)
                            function_id = self._get_function_id(path, node.spelling)
                            if function_id not in self.source_functions:
                                num_examples_added += 1
                            self.source_functions[function_id] = node_text
                    else:
                        log.warning(f"Failed to get text for {node.spelling} in {path}")
            if num_examples_added == 0:
                log.debug(f"No functions found in source file {path}")
                log.debug(f"  Diagnostics: {_pretty_diagnostics(source.diagnostics)}")
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
        num_examples_added = 0
        for function_name, function_text in chunk2(disassembled_components[1:]):
            _, function_text, _ = _split_function(function_text)
            function_id = self._get_function_id(path, function_name)
            if function_id not in self.disassembled_functions:
                num_examples_added += 1
            self.disassembled_functions[function_id] = function_text
        return num_examples_added

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
    def __init__(self, source_extensions, disassembled_extensions):
        super().__init__(source_extensions, [".o"], disassembled_extensions)
        self.index = Index.create()

    def source_extension_for(self, bytecode_or_disassembled_path: Path) -> str:
        return self.source_extensions[0]

    def ExampleDb(self) -> ExampleDb:
        return _CExampleDb()

    def process_source(self, source_data: Iterator[TransformStr]) -> str | bytes:
        return "\n\n".join(source_text.string for source_text in source_data)

    def process_disassembled(self, disassembled_path: Path) -> Iterator[TransformStr]:
        self._assert_disassembled_suffix(disassembled_path)
        disassembled_text, disassembled_source = _parse_source(disassembled_path, self.index)
        for node in disassembled_source.cursor.get_children():
            node_text = _node_text(disassembled_path, disassembled_text, node)
            if node_text is not None:
                if node.kind in FUNCTION_KINDS and '{' in node_text:
                    head, body, foot = _split_function(node_text)
                    yield TransformStr.pass_through(head)
                    yield TransformStr.regular(body)
                    yield TransformStr.pass_through(foot)
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


MISSING_IMPORT_REGEX = re.compile(r"^'(.*)' file not found$")
UNIT_OPTIONS = TranslationUnit.PARSE_INCOMPLETE | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES


def _parse_source(source_path: Path, clang_index: Index) -> (str, TranslationUnit):
    # currently clang_index.read and TranslationUnit#save are unused because reading an AST dump
    # sporadically throws SIGTRAP (macOS) or SIGSEGV (Linux)
    # (could use clang via spawning processes but at that point idk if there's any more performance gain)

    # Read the source text, since we must reference it anyways to get AST text
    with source_path.open("rb") as file:
        # We don't want to fail on non-utf8 files (which do exist in the data for some reason)
        text = file.read().decode("utf-8", errors="ignore")

    # Get parse args, also setup unsaved files dict
    default_include_paths = (path for path in chain([
        "/usr/include",
        "/usr/local/include",
        "/usr/include/x86_64-linux-gnu",
        "/opt/local/Cellar/include",
    ], os.environ.get("PARSE_EXTRA_INCLUDES", "").split(",")) if os.path.exists(path))
    local_include_paths = (str(path.resolve()) for path in source_path.parents)
    include_paths = chain(local_include_paths, default_include_paths)
    unit_args = list(chain(
        ["-ferror-limit=0"],
        (f"-I{path}" for path in include_paths)
    ))
    unit_unsaved_files = {}

    # Do parse the translation unit
    # noinspection PyShadowingNames
    def parse_translation_unit(text: str) -> TranslationUnit:
        return clang_index.parse(
            source_path,
            unsaved_files=list(chain([(source_path, text)], unit_unsaved_files.items())),
            args=unit_args,
            options=UNIT_OPTIONS
        )

    unit = parse_translation_unit(text)

    # Now, we might need to re-parse if clang encounters errors, since we are much more relaxed than clang,
    # and clang tends to completely fail when we still want to parse some of the data.
    # So the following functions modify the file so that we can potentially still get data from it
    # noinspection PyShadowingNames
    def remove_missing_imports(text: str, unit: TranslationUnit) -> (str, TranslationUnit, bool):
        try:
            # Get the missing import. clang only checks one import at a time.
            # If for some reason clang does multiple missing imports we run this iteratively anyways
            missing_import_origin_and_target: Optional[Tuple[Optional[File], str]] = next((
                (file, match.group(1))
                for file, match in (
                    (diagnostic.location.file, MISSING_IMPORT_REGEX.fullmatch(diagnostic.spelling))
                    for diagnostic in unit.diagnostics
                )
                if match is not None
            ), None)
            if missing_import_origin_and_target is None:
                return text, unit, False
            missing_import_origin, missing_import_target = missing_import_origin_and_target

            # Helpers to actually find and remove the missing import
            def is_line_missing_import(line: str) -> bool:
                return line.startswith(f"#") and "include" in line and missing_import_target in line

            # noinspection PyShadowingNames
            def remove_missing_import_from_text(text: str) -> Tuple[str, bool]:
                lines = text.splitlines()
                i = 0
                removed = False
                while i < len(lines):
                    line = lines[i]
                    if is_line_missing_import(line):
                        lines.pop(i)
                        removed = True
                    else:
                        i += 1
                return "\n".join(lines) if removed else text, removed

            # Do find and remove the missing import
            if missing_import_origin is None or str(missing_import_origin.name) == source_path.name:
                # Local missing import
                text, removed = remove_missing_import_from_text(text)
            else:
                # Missing import from another file
                missing_import_origin_name = missing_import_origin.name
                if missing_import_origin_name not in unit_unsaved_files:
                    with Path(missing_import_origin_name).open("rb") as file:
                        unit_unsaved_files[missing_import_origin_name] = file.read().decode("utf-8", errors="ignore")
                missing_import_origin_text = unit_unsaved_files[missing_import_origin_name]
                missing_import_origin_text, removed = remove_missing_import_from_text(missing_import_origin_text)
                unit_unsaved_files[missing_import_origin_name] = missing_import_origin_text

            # Check if removed, and if so, re-parse
            if not removed:
                log.warning(f"Failed to remove missing import from {source_path}: {missing_import_target}")
                return text, unit, False
            unit = parse_translation_unit(text)
            return text, unit, True
        except Exception as e:
            raise Exception("Error parsing after removing missing imports") from e

    # noinspection PyShadowingNames
    def remove_surrounding_ifdef(text: str, unit: TranslationUnit) -> (str, TranslationUnit):
        try:
            lines = text.splitlines()
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
            unit = parse_translation_unit(text)
            return text, unit
        except Exception as e:
            raise Exception("Error parsing after removing surrounding #ifdef") from e

    # The exact process to get more information from the file:
    # - If the entire code is wrapped in #ifdef or #if, we will remove it
    # - If there are missing imports, we will remove them until there are no more or we make no progress
    # May need to remove missing imports after we find #ifdef, but can remove #ifdef before missing imports
    if next(unit.cursor.get_children(), None) is None:
        text, unit = remove_surrounding_ifdef(text, unit)
    while True:
        text, unit, removed = remove_missing_imports(text, unit)
        if not removed:
            break

    # Done
    return text, unit


def _node_text(source_path: Path, text: str, node: Cursor) -> Optional[str]:
    extent: SourceRange = node.extent
    if extent.start.file is None:
        return None
    path = extent.start.file.name
    if path != str(source_path):
        with open(path, "rb") as file:
            text = file.read().decode("utf-8", errors="ignore")
    return text[extent.start.offset:extent.end.offset]


def _split_function(node_text: str) -> Tuple[str, str, str]:
    head, body_foot = node_text.split("{", 1)
    if '}' in body_foot:
        body, foot = body_foot.rsplit("}", 1)
        return head + "{", body, "}" + foot
    else:
        return head + "{", body_foot, ""


def _pretty_diagnostics(diagnostics: Iterator[Diagnostic]) -> str:
    return "\n\t".join(_pretty_diagnostic(diagnostic) for diagnostic in diagnostics)


def _pretty_diagnostic(diagnostic: Diagnostic) -> str:
    diagnostic_file = \
        f"{diagnostic.location.file.name}:{diagnostic.location.line}:{diagnostic.location.column}" \
        if diagnostic.location.file is not None else "<no-file>"
    return f"{diagnostic.severity}[{diagnostic_file}]: {diagnostic.spelling} "

class CCodeType(_CCodeType):
    def __init__(self):
        super().__init__([".c", ".h"], [".o.c"])

    def __str__(self):
        return "C"

    def __reduce__(self):
        return CCodeType, ()


class CppCodeType(_CCodeType):
    def __init__(self):
        super().__init__(
            [".c", ".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp"],
            [".o.c", ".o.cpp", ".o.cc", ".o.cxx", ".o.c++"]
        )

    def __str__(self):
        return "C/C++"

    def __reduce__(self):
        return CppCodeType, ()


def configure_clang():
    # On macOS, the default clang installation is not in the path, but is in the CommandLineTools
    if sys.platform == "darwin" and os.path.isfile("/Library/Developer/CommandLineTools/usr/lib/libclang.dylib"):
        Config.set_library_file("/Library/Developer/CommandLineTools/usr/lib/libclang.dylib")


configure_clang()
