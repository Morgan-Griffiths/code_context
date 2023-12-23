import ast
from typing import Optional
from pydantic import BaseModel
from response_types import Range, Position
import importlib.util


def get_module_file_path(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec is not None:
        return spec.origin
    else:
        return None


def find_function_range(file_uri: str, function_name: str) -> Optional[Range]:
    with open(file_uri) as f:
        source_code = f.read()

    class FunctionVisitor(ast.NodeVisitor):
        def __init__(self, function_name):
            self.function_name = function_name
            self.span = None

        def visit_FunctionDef(self, node):
            if node.name == self.function_name:
                start_line = node.lineno
                end_line = getattr(node, "end_lineno", None)
                start_char = node.col_offset
                end_char = getattr(node, "end_col_offset", None)
                self.span = (start_line, end_line, start_char, end_char)
            self.generic_visit(node)

    tree = ast.parse(source_code)
    visitor = FunctionVisitor(function_name)
    visitor.visit(tree)
    if visitor.span is None:
        return None
    return Range(
        start=Position(
            line=visitor.span[0] - 1, character=visitor.span[2] + 4
        ),  # +4 to account for "def "
        end=Position(line=visitor.span[1] - 1, character=visitor.span[3]),
    )


class ImportInfo(BaseModel):
    file_path: str
    module_name: Optional[str]
    line: int
    character: int


def extract_imports_info(ast_imports: Optional[list[ast.AST]]) -> list[ImportInfo]:
    imports_info = []
    for node in ast_imports:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports_info.append(
                    ImportInfo(
                        file_path=alias.name,
                        module_name=None,
                        line=node.lineno - 1,  # -1 to account for 0-indexing
                        character=node.col_offset + 8,  # +8 to account for "import "
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            for alias in node.names:
                imports_info.append(
                    ImportInfo(
                        file_path=get_module_file_path(module),
                        module_name=alias.name,
                        line=node.lineno - 1,  # -1 to account for 0-indexing
                        character=node.col_offset
                        + 6,  # +6 to account for "from " and "import "
                    )
                )
    return imports_info


def find_top_level_imports_ast(file_content) -> list[ImportInfo]:
    tree = ast.parse(file_content)
    return extract_imports_info(
        [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom)
        ]
    )


def find_imports_in_function(file_content, function_name) -> Optional[list[ImportInfo]]:
    tree = ast.parse(file_content)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            for n in ast.walk(node):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    imports.append(extract_imports_info([n]))
    return imports


def filter_imports(imports: list[ImportInfo]):
    return [
        m
        for m in imports
        if ".pyenv" not in m.file_path
        and ".virtualenvs" not in m.file_path
        and m.module_name is not None
    ]
