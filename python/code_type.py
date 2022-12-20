from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Tuple

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