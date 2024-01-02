import ast
from typing import Optional
from code_context.response_types import (
    ImportInfo,
    Range,
    Position,
    NodeInfo,
    VisitedNode,
)
import builtins
import importlib.util

from code_context.utils import read_file_uri


def get_builtin_methods_for_types(*types) -> set[str]:
    """Return a set of names of all methods of the given built-in types."""
    methods = set()
    for t in types:
        methods.update(dir(t))
    return methods


BUILTIN_METHODS = get_builtin_methods_for_types(str, dict, list, set, int, float, tuple)


def find_node_at_position(
    file_content: str, lsp_line_no: int, function_name: str
) -> Optional[ast.AST]:
    """Find the AST node at the given line and character number"""
    tree = ast.parse(file_content)
    for node in ast.walk(tree):
        if hasattr(node, "lineno"):
            if node.lineno == (lsp_line_no + 1):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id == function_name:
                            return node
                    elif isinstance(node.func, ast.Attribute):
                        # Method call or namespaced function call like obj.method()
                        node = node.func
                        while isinstance(node, ast.Attribute):
                            node = node.value
                        if isinstance(node, ast.Name) and node.id == function_name:
                            return node
                        elif (
                            isinstance(node, ast.Attribute)
                            and node.attr == function_name
                        ):
                            return node
                elif isinstance(node, ast.Attribute):
                    while isinstance(node.value, ast.Attribute):
                        node = node.value
                    if isinstance(node, ast.Attribute) and node.attr == function_name:
                        return node
                    elif isinstance({node}, ast.Name) and node.id == function_name:
                        return node
                elif isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    return node
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == function_name:
                            return node
    return None


def extract_code_segment(file_content, node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        # skips immediately preceding comments, as they are not part of the ast
        start_line = node.lineno
        if node.decorator_list:
            start_line -= len(node.decorator_list)
        end_line = node.end_lineno if hasattr(node, "end_lineno") else start_line
    elif isinstance(node, ast.Assign):
        start_line = node.lineno
        end_line = start_line
    else:
        print("node returned None", node)
        return None  # Or handle other types as needed
    lines = file_content.splitlines()
    return "\n".join(lines[start_line - 1 : end_line])


class TopLevelVisitor(ast.NodeVisitor):
    def __init__(self, uri):
        self.file_uri = uri
        self.top_level_definitions: list[NodeInfo] = []

    def visit_FunctionDef(self, node):
        self.top_level_definitions.append(
            NodeInfo(
                uri=self.file_uri,
                node=node,
            )
        )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.top_level_definitions.append(
            NodeInfo(
                uri=self.file_uri,
                node=node,
            )
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.top_level_definitions.append(
            NodeInfo(
                uri=self.file_uri,
                node=node,
            )
        )
        self.generic_visit(node)

    def _get_span(self, node):
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        start_char = node.col_offset
        end_char = getattr(node, "end_col_offset", start_char)
        return Range(
            start=Position(line=start_line, character=start_char),
            end=Position(line=end_line, character=end_char),
        )


def find_top_level_definitions(file_path) -> list[NodeInfo]:
    with open(file_path, "r") as file:
        content = file.read()

    tree = ast.parse(content)
    visitor = TopLevelVisitor(uri="file://" + file_path)
    visitor.visit(tree)
    return visitor.top_level_definitions


def find_function_or_class_range(file_uri: str, object_name: str) -> Optional[NodeInfo]:
    """works for functions and classes"""
    with open(file_uri) as f:
        source_code = f.read()

    class FunctionVisitor(ast.NodeVisitor):
        def __init__(self, object_name):
            self.object_name = object_name
            self.object_details = None

        def visit_FunctionDef(self, node):
            if node.name == self.object_name:
                self.object_details = NodeInfo(
                    uri=file_uri,
                    node=node,
                )

        def visit_AsyncFunctionDef(self, node):
            if node.name == self.object_name:
                self.object_details = NodeInfo(
                    uri=file_uri,
                    node=node,
                )

        def visit_ClassDef(self, node):
            if node.name == self.object_name:
                self.object_details = NodeInfo(
                    uri=file_uri,
                    node=node,
                )

        def _get_span(self, node):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)
            start_char = node.col_offset
            end_char = getattr(node, "end_col_offset", start_char)
            return Range(
                start=Position(line=start_line - 1, character=start_char + 4),
                end=Position(line=end_line - 1, character=end_char),
            )

    tree = ast.parse(source_code)
    visitor = FunctionVisitor(object_name)
    visitor.visit(tree)
    if visitor.object_details is None:
        return None
    return visitor.object_details


def find_all_method_and_function_calls(node_info: NodeInfo) -> set[VisitedNode]:
    """Given a file and function or class name, finds all the method and function calls inside that function"""
    calls: set[VisitedNode] = set()
    tree = ast.parse(read_file_uri(node_info.uri))
    for fnode in ast.walk(tree):
        if (
            isinstance(fnode, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and fnode.name == node_info.node.name
        ):
            for node in ast.walk(fnode):
                if isinstance(node, ast.Call):
                    # For function/method calls, get the function/method name. Exclude builtins.
                    if isinstance(node.func, ast.Name) and node.func.id not in dir(
                        builtins
                    ):
                        # Direct function call like foo()
                        calls.add(
                            VisitedNode(
                                uri=node_info.uri,
                                name=node.func.id,
                                line=node.lineno - 1,
                                character=node.col_offset + 1,
                            ),
                        )
                    elif (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr not in BUILTIN_METHODS
                    ):
                        # Method call or namespaced function call like obj.method()
                        calls.add(
                            VisitedNode(
                                uri=node_info.uri,
                                name=node.func.attr,
                                line=node.lineno - 1,
                                character=node.func.end_col_offset,
                            )
                        )
            break
    return calls


def filter_out_builtins_from_locations(node_information: list[NodeInfo]):
    return [
        m
        for m in node_information
        if ".pyenv" not in m.uri and ".virtualenvs" not in m.uri
    ]


#####################################
######### UNUSED FUNCTIONS ##########
#####################################


def find_top_level_imports_ast(file_content) -> list[ImportInfo]:
    tree = ast.parse(file_content)
    return extract_imports_info(
        [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom)
        ]
    )


def get_module_file_path(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec is not None:
        return spec.origin
    else:
        return None


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
