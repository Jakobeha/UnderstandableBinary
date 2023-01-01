from glob import glob
from itertools import chain, islice
from os import environ, path
from pathlib import Path
from typing import Iterable, Optional

from tree_sitter import Language, Parser, Tree
from tree_sitter.binding import Node

from utils import PROJECT_PATH, chunk2, walk_files_up_to_depth, all_but_last

# region init
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


# endregion

class _TreeSitterQueries:
    def __init__(self, language: Language, function_query: str, include_query: str):
        self.function = language.query(function_query)
        self.include = language.query(include_query)


class TreeSitterFunction:
    def __init__(self, name: str, text: str):
        self.name = name
        self.text = text


_QUERIES: dict[Language, _TreeSitterQueries] = {
    C_LANGUAGE: _TreeSitterQueries(C_LANGUAGE, """
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @fn_name
  )
) @fn
""", """
(preproc_include
  [
    (string_literal) @include
    (system_lib_string) @system_include
  ]
)
"""),
    CPP_LANGUAGE: _TreeSitterQueries(CPP_LANGUAGE, """
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
""", """
(preproc_include
  [
    (string_literal) @include
    (system_lib_string) @system_include
  ]
)
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


def scrape_functions(source_path: Path, lang: Language, parser: Parser) -> Iterable[TreeSitterFunction]:
    parser.set_language(lang)
    with source_path.open("rb") as source_file:
        source_bytes = source_file.read()
    queries = _QUERIES[lang]
    tree: Tree = parser.parse(source_bytes)
    return _scrape_functions(source_path, lang, parser, tree, queries)


def _scrape_functions(
        source_path: Path,
        lang: Language,
        parser: Parser,
        tree: Tree,
        queries: _TreeSitterQueries) -> Iterable[TreeSitterFunction]:
    return chain(
        _scrape_local_functions(tree, queries),
        _scrape_imported_functions(source_path, lang, parser, tree, queries)
    )


def _scrape_local_functions(tree: Tree, queries: _TreeSitterQueries) -> Iterable[TreeSitterFunction]:
    captures: list[tuple[Node, str]] = queries.function.captures(tree.root_node)
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


def _scrape_imported_functions(
        source_path: Path,
        lang: Language,
        parser: Parser,
        tree: Tree,
        queries: _TreeSitterQueries) -> Iterable[TreeSitterFunction]:
    captures: list[tuple[Node, str]] = queries.include.captures(tree.root_node)
    for capture in captures:
        is_system_include = capture[1] == "system_include"
        include_path_str = capture[0].text.decode("utf-8", errors="ignore")
        include_path = _resolve_include_path(source_path, include_path_str, is_system_include)
        if include_path is not None:
            yield from scrape_functions(include_path, lang, parser)


_LIBRARY_DIRS: list[Path] = [Path(path_str) for path_str in chain(
    environ.get("LIBRARY_DIRS", "").split(","),
    [
        "/usr/include",
        "/usr/local/include",
        "/opt/local/include",
        "/opt/homebrew/include",
        "/mingw64/include",
        "/mingw32/include",
        "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include",
        "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/c++/v1",
    ],
    glob("/usr/lib/clang/*/include"),
    glob("/usr/lib/gcc/x86_64-linux-gnu/*/include")
) if path.isdir(path_str)]

LOCAL_INCLUDE_CHILD_DEPTH = int(environ.get("LOCAL_INCLUDE_CHILD_DEPTH", "0"))


def _resolve_include_path(source_path: Path, include_path_str: str, is_system_include: bool) -> Optional[Path]:
    include_path = Path(include_path_str)

    # Root dir is not going to be a parent
    def reasonable_parents() -> Iterable[Path]:
        return all_but_last(source_path.parents)

    if not is_system_include:
        # Resolve locally
        # First try just parents
        for parent in reasonable_parents():
            try:
                full_include_path = parent / include_path
                if full_include_path.exists():
                    return full_include_path
            except PermissionError:
                pass
        # If it fails, try children of parents (relatives...uncles/aunts/cousins?)
        if LOCAL_INCLUDE_CHILD_DEPTH > 0:
            for parent in reasonable_parents():
                # note that the first returned is the parent itself
                try:
                    for relative in islice(walk_files_up_to_depth(parent, LOCAL_INCLUDE_CHILD_DEPTH), 1, None):
                        # also note that not all relatives are directories
                        if relative.is_dir():
                            full_include_path = relative / include_path
                            if full_include_path.exists():
                                return full_include_path
                except PermissionError:
                    pass
    # Resolve from system
    for library_dir in _LIBRARY_DIRS:
        try:
            full_include_path = library_dir / include_path
            if full_include_path.exists():
                return full_include_path
        except PermissionError:
            pass
    return None
