import ast
import os
from typing import Optional
from ast_parsing import (
    extract_imports_info,
    filter_imports,
    find_top_level_imports_ast,
)
from lsp_client import LSPWebSocketClient
from response_types import (
    DocumentSymbol,
    ImportInfo,
    Location,
    Position,
    Range,
    TextDocument,
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


def filter_out_inside_function_symbols(
    symbols: list[DocumentSymbol], filename: str, function_range: Range
) -> list[Location]:
    external_symbols = []
    for symbol in symbols:
        if symbol.location.uri != f"file://{filename}":
            print("symbol.location", symbol.location.uri)
        if (
            symbol.location.uri != f"file://{filename}"
            and ".pyenv" not in symbol.location.uri
            and ".virtualenvs" not in symbol.location.uri
        ):
            external_symbols.append(symbol.location)
        elif (
            symbol.location.range.end.line < function_range.start.line
            or symbol.location.range.start.line > function_range.end.line
        ):
            external_symbols.append(symbol.location)
    return external_symbols


def find_function_position(filename, function_name) -> Optional[Position]:
    with open(filename, "r") as file:
        for line_num, line in enumerate(file, start=1):
            if f"def {function_name}(" in line:
                return Position(
                    line=line_num - 1,
                    character=line.find(f"def {function_name}") + 4,
                )
    return None


async def get_function_range(
    client: LSPWebSocketClient, filename: str, function_name: str
) -> Optional[DocumentSymbol]:
    symbols_in_scope = await client.get_document_symbol(filename)
    for symbol in symbols_in_scope:
        if symbol.name == function_name:
            print("symbol", symbol)
    return None


async def get_relevant_modules(
    client, function_name, file_content, function_range, text_document
):
    function_level_imports = find_imports_in_function(file_content, function_name)
    top_level_imports = find_top_level_imports_ast(file_content)
    filtered_modules = filter_imports(top_level_imports)
    relevant_modules = []
    for tl_import in filtered_modules:
        refs = await client.get_references(
            text_document,
            Position(line=tl_import.line, character=tl_import.character + 1),
        )
        # store refs that are referenced inside the function
        if refs.result:
            for r in refs.result:
                if (
                    r.range.start.line >= function_range.start.line
                    and r.range.end.line <= function_range.end.line
                ):
                    relevant_modules.append(tl_import)
                    break
    return relevant_modules + function_level_imports


class LSPPlaceHolderClient(LSPWebSocketClient):
    async def find_function_definition(self, filename: str, function_name: str):
        if not os.path.exists(filename):
            print("File does not exist.")
            return
        if self.connection is None:
            print("Not connected to server.")
            return
        position = find_function_position(filename, function_name)
        if position is None:
            print("Function not found in the file.")
            return
        text_document = TextDocument(uri=f"file://{filename}")
        response = await self.get_definition(text_document, position)
        return response
