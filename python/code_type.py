from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Tuple

ModelStr = str


class ExampleDb(ABC):
    @abstractmethod
    def add_source(self, path: Path):
        pass

    def add_disassembled(self, path: Path):
        pass

    @abstractmethod
    def build(self) -> Iterator[Tuple[ModelStr, ModelStr]]:
        raise NotImplementedError("abstract")


class CodeType(ABC):
    def __init__(self, source_extensions, bytecode_extensions, disassembled_extensions):
        self.source_extensions = source_extensions
        self.bytecode_extensions = bytecode_extensions
        self.disassembled_extensions = disassembled_extensions

    # noinspection PyPep8Naming
    @abstractmethod
    def ExampleDb(self) -> ExampleDb:
        raise NotImplementedError("abstract")

    @abstractmethod
    def source_extension_for(self, bytecode_or_disassembled_path: Path) -> str:
        raise NotImplementedError("abstract")

    def process_source(self, output_data: Iterator[ModelStr]) -> str | bytes:
        raise NotImplementedError("abstract")

    @abstractmethod
    def process_disassembled(self, input_path: Path) -> Iterator[ModelStr]:
        raise NotImplementedError("abstract")