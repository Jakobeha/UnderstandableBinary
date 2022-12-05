class CodeType:
    def __init__(self, source_extension, bytecode_extensions):
        self.source_extension = source_extension
        self.bytecode_extensions = bytecode_extensions


CODE_TYPE_C = CodeType(".c", [".s", ".o", ".o.c"])

CODE_TYPES = {
    "c": CODE_TYPE_C
}