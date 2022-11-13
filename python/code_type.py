class CodeType:
    def __init__(self, source_extension, bytecode_extension, alt_bytecode_extension=None):
        self.source_extension = source_extension
        self.bytecode_extension = bytecode_extension
        self.alt_bytecode_extension = alt_bytecode_extension


CodeType.C = CodeType(".c", ".s", ".o")

CODE_TYPES = {
    "c": CodeType.C
}