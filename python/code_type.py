from abc import ABC, abstractmethod
from pathlib import Path
import re
from typing import Iterator, Tuple

from python.log import log
from python.utils import chunk2

ModelStr = str


class CodeType(ABC):
    def __init__(self, source_extensions, bytecode_extensions, disassembled_extensions):
        self.source_extensions = source_extensions
        self.bytecode_extensions = bytecode_extensions
        self.disassembled_extensions = disassembled_extensions

    @abstractmethod
    def source_extension_for(self, bytecode_or_disassembled_path: Path) -> str:
        raise NotImplementedError("abstract")

    @abstractmethod
    def process_training(self, input_path: Path, expected_path: Path) -> Iterator[Tuple[ModelStr, ModelStr]]:
        raise NotImplementedError("abstract")

    @abstractmethod
    def process_input(self, input_path: Path) -> Iterator[ModelStr]:
        raise NotImplementedError("abstract")

    def process_output(self, output_data: Iterator[ModelStr]) -> str | bytes:
        raise NotImplementedError("abstract")


class CCodeType(CodeType):
    def __init__(self):
        super().__init__([".c"], [".o"], [".o.c"])

    def source_extension_for(self, bytecode_or_disassembled_path: Path) -> str:
        return ".c"

    def process_training(self, input_path: Path, expected_path: Path) -> Iterator[Tuple[ModelStr, ModelStr]]:
        self._assert_disassembled_suffix(input_path)
        self._assert_source_suffix(expected_path)
        if input_path.stat().st_size == 0:
            # Some files are empty (file existence tells Ghidra to ignore, but there is nothing extractable)
            log.debug(f"Skipping empty file {input_path}")
            return
        with input_path.open(encoding="utf8") as input_file:
            with expected_path.open(encoding="utf8") as expected_file:
                input_data = input_file.read()
                expected_data = expected_file.read()
                # Functions in disassembled code are already denoted
                input_components = re.split(r"^// FUNCTION (\w+)$", input_data, flags=re.MULTILINE)
                if len(input_components) < 2:
                    # File has no functions
                    raise Exception("Bad input data format: " + "\n\n".join(input_components))
                for function_name, function_data in chunk2(input_components[1:]):
                    # Super dumb regex which should handle nearly all ways function_name would be defined in actual code
                    expected_function = re.search(
                        r"^.*[^\S\r\n]*" + re.escape(function_name) + r"\s*\([^)]*\)\s*\{.*^}$",
                        expected_data,
                        flags=re.MULTILINE
                    )
                    if expected_function is None:
                        log.debug(
                            f"Failed to find disassembled function {function_name} in expected output "
                            f"{str(expected_path)}"
                        )
                        continue
                    yield ModelStr(function_data), ModelStr(expected_function.group(0))

    def process_input(self, input_path: Path) -> Iterator[ModelStr]:
        self._assert_disassembled_suffix(input_path)
        with input_path.open(encoding="utf8") as input_file:
            input_data = input_file.read()
            # Use the same dumb regex as above
            # Maybe someday we'll use a real C parser, but as long as it handles Ghidra disassembly it's good enough
            for input_function in re.finditer(
                r"^.*\s*\w+\s*\([^)]*\)\s*\{.*^}$",
                input_data,
                flags=re.MULTILINE
            ):
                yield ModelStr(input_function.group(0))

    def process_output(self, output_data: Iterator[ModelStr]) -> str | bytes:
        return "\n\n".join(output_data)

    def _assert_source_suffix(self, input_path: Path):
        if not any(input_path.name.endswith(src_ext) for src_ext in self.source_extensions):
            raise ValueError(f"Expected source suffix, got {input_path.suffix}")

    def _assert_disassembled_suffix(self, disassembled_path: Path):
        if not any(disassembled_path.name.endswith(dis_ext) for dis_ext in self.disassembled_extensions):
            raise ValueError(
                f"Expected disassembled suffix, got {disassembled_path.suffix} (TODO: decompile bytecode using Ghidra "
                f"so that we also accept)"
            )


CODE_TYPES = {
    "c": CCodeType()
}
