import ast
from typing import Optional
from pydantic import BaseModel
from response_types import Location, Range, Position
import importlib.util


class ImportInfo(BaseModel):
    file_path: str
    module_name: Optional[str]
    line: int
    character: int


class CallInfo(BaseModel):
    function_name: str
    line: int
    character: int

    def __hash__(self):
        return hash((self.function_name, self.line, self.character))

    def __eq__(self, other):
        if isinstance(other, CallInfo):
            return (
                self.function_name == other.function_name
                and self.line == other.line
                and self.character == other.character
            )
        return False


def find_node_at_position(file_content, lsp_line_no):
    """Find the AST node at the given line and character number"""
    tree = ast.parse(file_content)
    for node in ast.walk(tree):
        if hasattr(node, "lineno"):
            if node.lineno == (lsp_line_no + 1):
                return node
    return None


def extract_code_segment(file_content, node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        start_line = max(node.lineno - 2, 0)
        end_line = node.end_lineno if hasattr(node, "end_lineno") else start_line
    elif isinstance(node, ast.Assign):
        start_line = node.lineno
        end_line = start_line
    else:
        return None  # Or handle other types as needed

    lines = file_content.splitlines()
    return "\n".join(lines[start_line - 1 : end_line])


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


def extract_imports_info(ast_imports: Optional[list[ast.AST]]) -> list[ImportInfo]:
    """Extracts the file path, module name, line number and character number from an AST Import or ImportFrom node"""
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


def find_all_method_and_function_calls(file_content, target_name) -> set[CallInfo]:
    """Given a file and function or class name, finds all the method and function calls inside that function"""
    calls = set()
    tree = ast.parse(file_content)
    for fnode in ast.walk(tree):
        if (
            isinstance(fnode, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and fnode.name == target_name
        ):
            for node in ast.walk(fnode):
                if isinstance(node, ast.Attribute):
                    # Grabbing the last attribute in a dotted expression
                    while isinstance(node.value, ast.Attribute):
                        node = node.value
                    calls.add(
                        CallInfo(
                            function_name=node.attr,
                            line=node.lineno - 1,
                            character=node.col_offset + len(node.attr) + 1,
                        ),
                    )
                elif isinstance(node, ast.Call):
                    # For function/method calls, get the function/method name
                    if isinstance(node.func, ast.Name):
                        # Direct function call like foo()
                        calls.add(
                            CallInfo(
                                function_name=node.func.id,
                                line=node.lineno - 1,
                                character=node.col_offset,
                            ),
                        )
                    elif isinstance(node.func, ast.Attribute):
                        # print(node.func.attr, node.func.col_offset)
                        # Method call or namespaced function call like obj.method()
                        calls.add(
                            CallInfo(
                                function_name=node.func.attr,
                                line=node.lineno - 1,
                                character=node.func.col_offset
                                + len(node.func.attr)
                                + 1,
                            )
                        )
            break
    return calls


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
            break
    return imports


def filter_locations(locations: list[Location]):
    return [
        m for m in locations if ".pyenv" not in m.uri and ".virtualenvs" not in m.uri
    ]


def filter_imports(imports: list[ImportInfo]):
    return [
        m
        for m in imports
        if ".pyenv" not in m.file_path
        and ".virtualenvs" not in m.file_path
        and m.module_name is not None
    ]
