from pathlib import Path
from typing import Iterable

from tree_sitter import Language, Parser, Tree
from tree_sitter.binding import Query, Node

from utils import PROJECT_PATH, chunk2

TREE_SITTER_SO_PATH = PROJECT_PATH / "local/tree-sitter-languages.so"
TREE_SITTER_VENDOR_PATH = PROJECT_PATH / "vendor"


def setup():
    TREE_SITTER_SO_PATH.parent.mkdir(parents=True, exist_ok=True)
    Language.build_library(
        str(TREE_SITTER_SO_PATH),
        [
            str(TREE_SITTER_VENDOR_PATH / "tree-sitter-c"),
            str(TREE_SITTER_VENDOR_PATH / "tree-sitter-cpp")
        ]
    )


setup()

C_LANGUAGE = Language(str(TREE_SITTER_SO_PATH), 'c')
CPP_LANGUAGE = Language(str(TREE_SITTER_SO_PATH), 'cpp')

_C_FN_QUERY = """
(
    (function_definition
        name: (identifier)) @function
)
"""

FUNCTION_QUERIES: dict[Language, Query] = {
    C_LANGUAGE: C_LANGUAGE.query("""
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @fn_name
  )
) @fn
"""),
    CPP_LANGUAGE: CPP_LANGUAGE.query("""
(function_definition
  declarator: [
    (function_declarator
      declarator: [
        (qualified_identifier name: (identifier) @fn_name)
        (identifier) @fn_name
        (field_identifier) @fn_name
      ]
    )
    (reference_declarator
      (function_declarator
        declarator: [
          (qualified_identifier name: (identifier) @fn_name)
          (identifier) @fn_name
          (field_identifier) @fn_name
        ]
      )
    )
  ]
) @fn
""")
}

# Alternative CPP_LANGUAGE query which is not used because it doesn't produce an even number of captures
# (multiple identifiers?)
# (function_definition
#   declarator: (_ [
#     (qualified_identifier name: (identifier) @fn_name)
#     (identifier) @fn_name
#     (field_identifier) @fn_name
#   ])
# ) @fn


class TreeSitterFunction:
    def __init__(self, name: str, text: str):
        self.name = name
        self.text = text


def scrape_functions(source_path: Path, lang: Language, parser: Parser) -> Iterable[TreeSitterFunction]:
    parser.set_language(lang)
    with source_path.open("rb") as source_file:
        source_bytes = source_file.read()
    query = FUNCTION_QUERIES[lang]
    tree: Tree = parser.parse(source_bytes)
    captures: list[tuple[Node, str]] = query.captures(tree.root_node)
    if len(captures) % 2 == 0 and \
            all(fn[1] == "fn" and fn_name[1] == "fn_name" for fn, fn_name in chunk2(captures)):
        # Fastpath, all files should follow this but there is some weird bug or edge case I don't get
        for fn, fn_name in chunk2(captures):
            fn2 = fn[0]
            fn_name2 = fn_name[0]
            yield TreeSitterFunction(
                fn_name2.text.decode("utf-8", errors="ignore"),
                fn2.text.decode("utf-8", errors="ignore"),
            )
    else:
        # Slowpath
        fn = None
        for capture in captures:
            if capture[1] == "fn":
                fn = capture[0]
            else:
                assert capture[1] == "fn_name"
                assert fn is not None
                fn_name = capture[0]
                yield TreeSitterFunction(
                    fn_name.text.decode("utf-8", errors="ignore"),
                    fn.text.decode("utf-8", errors="ignore"),
                )
