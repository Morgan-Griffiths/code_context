import asyncio
from enum import Enum
from typing import Optional
import websockets
import json
import os
import sys
import time
import subprocess
from pydantic import BaseModel
import uuid
from response_types import (
    DocumentSymbol,
    FindReferencesResponse,
    DefinitionResponse,
    GoToDeclarationResponse,
    GoToImplementationResponse,
    Location,
    Range,
    TypeDefinitionResponse,
    TypeDefinitionResponse,
    DocumentSymbolResponse,
    ReferenceContext,
    ReferenceParams,
    TextDocument,
    Position,
)

from ast_parsing import (
    find_function_range,
    find_top_level_imports_ast,
    find_imports_in_function,
    filter_imports,
)


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Enum):
            return o.value  # Convert Enum to its value
        if isinstance(o, BaseModel):
            return o.dict(by_alias=True)
        return super().default(o)


class LSPWebSocketClient:
    def __init__(self, uri):
        self.uri = uri
        self.connection = None

    def _generate_unique_id(self):
        return str(uuid.uuid4())

    async def connect(self):
        self.connection = await websockets.connect(self.uri)

    async def send_message(self, message):
        await self.connection.send(json.dumps(message, cls=EnhancedJSONEncoder))

    async def receive_message(self):
        return json.loads(await self.connection.recv())

    async def send_request(self, method: str, params: dict, request_id=None):
        if request_id is None:
            request_id = self._generate_unique_id()
        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        await self.send_message(message)
        return await self.receive_message()

    async def close(self):
        await self.connection.close()

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

    async def go_to_declaration(self, text_document: TextDocument, position: Position):
        response = await self.send_request(
            "textDocument/declaration",
            {"textDocument": text_document, "position": position},
        )
        return GoToDeclarationResponse(**response)

    async def get_type_definition(
        self, text_document: TextDocument, position: Position
    ):
        response = await self.send_request(
            "textDocument/typeDefinition",
            {"textDocument": text_document, "position": position},
        )
        return TypeDefinitionResponse(**response)

    async def go_to_implementation(
        self, text_document: TextDocument, position: Position
    ):
        response = await self.send_request(
            "textDocument/implementation",
            {"textDocument": text_document, "position": position},
        )
        return GoToImplementationResponse(**response)

    async def get_references(self, text_document: TextDocument, position: Position):
        """ """
        params = ReferenceParams(
            text_document=text_document,
            position=position,
            context=ReferenceContext(includeDeclaration=True),
        )
        response = await self.send_request(
            "textDocument/references",
            params,
        )
        return FindReferencesResponse(**response)

    async def get_document_symbol(
        self, filename: str
    ) -> Optional[list[DocumentSymbol]]:
        text_document = TextDocument(uri=f"file://{filename}")
        response = await self.send_request(
            "textDocument/documentSymbol",
            {"textDocument": text_document},
        )
        return DocumentSymbolResponse(**response).result

    async def get_definition(
        self, text_document: TextDocument, position: Position
    ) -> DefinitionResponse:
        response = await self.send_request(
            "textDocument/definition",
            {"textDocument": text_document, "position": position},
        )
        return DefinitionResponse(**response)

    async def get_completion(self, text_document: TextDocument, position: Position):
        response = await self.send_request(
            "textDocument/completion",
            {"textDocument": text_document, "position": position},
        )
        return response


async def get_function_range(
    client: LSPWebSocketClient, filename: str, function_name: str
) -> Optional[DocumentSymbol]:
    symbols_in_scope = await client.get_document_symbol(filename)
    for symbol in symbols_in_scope:
        if symbol.name == function_name:
            print("symbol", symbol)
    return None


async def get_relevant_modules(client, file_content, function_range, text_document):
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


async def get_function_context(
    client: LSPWebSocketClient, filename: str, function_name: str
):
    with open(filename, "r") as file:
        file_content = file.read()
    # Initial setup: Find function position, etc.
    text_document = TextDocument(uri=f"file://{filename}")
    function_range = find_function_range(filename, function_name)
    if function_range is None:
        print("Function not found in the file.")
        sys.exit(1)

    relevant_modules = await get_relevant_modules(
        client, file_content, function_range, text_document
    )

    first_module = relevant_modules[1]
    print("first_module", first_module)
    symbols = await client.get_definition(
        text_document=text_document,
        position=Position(line=first_module.line, character=first_module.character),
    )
    print("symbols", symbols)
    second = await client.get_definition(
        text_document=text_document,
        position=Position(
            line=symbols.result[0].range.start.line,
            character=symbols.result[0].range.start.character,
        ),
    )
    print("second", second)
    # print("relevant_modules", relevant_modules)

    # Step 1: find all the definitions of the top level imports
    # for module in relevant_modules:
    #     definition = await client.get_definition(
    #         text_document,
    #         Position(line=module.line, character=module.character),
    #     )
    #     print("definition", definition)

    # find all the definitions of the function level imports
    # print(filtered_modules)
    # print(function_level_imports)
    # Step 1: get symbols within the function
    # symbols_in_scope = await client.get_document_symbol(filename)
    # print("symbols_in_scope", symbols_in_scope)
    # filter for symbols outside of the function

    # ref = await client.get_references(text_document, symbol.location.range.start)
    # if ref.result:
    #     symbol_references.append(ref.result[0])
    # external_symbols = filter_out_inside_function_symbols(
    #     symbols_in_scope, filename, function_range
    # )

    # print("external_symbols", external_symbols)
    # unique_uris = {ref.uri for ref in external_symbols}
    # print(f"unique_uris: {unique_uris}, len: {len(unique_uris)}")

    # Step 2: Find external references
    # external_references = await client.get_references(text_document, position)
    # print("external_references", external_references)
    # filter out references in the same file
    # external_references = [
    #     ref for ref in external_references.result if ref.uri != f"file://{filename}"
    # ]
    # print("external_references", external_references)
    # Step 3: Extract relevant code blocks
    # ...

    # Step 4: Combine the extracted code into a single context block
    # ...
    combined_context = ""
    return combined_context


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
    # return [
    #     symbol
    #     for symbol in symbol_refs
    #     if symbol.location.uri != f"file://{filename}"
    #     and ".pyenv" not in symbol.location.uri
    #     and ".virtualenvs" not in symbol.location.uri
    #     and (
    #         symbol.location.range.end.line < function_range.start.line
    #         or symbol.location.range.start.line > function_range.end.line
    #     )  # defined outside of the function
    # ]


def find_function_position(filename, function_name) -> Optional[Position]:
    with open(filename, "r") as file:
        for line_num, line in enumerate(file, start=1):
            if f"def {function_name}(" in line:
                return Position(
                    line=line_num - 1,
                    character=line.find(f"def {function_name}") + 4,
                )
    return None


URI = "ws://0.0.0.0:2087"


# Example usage
async def main(filename, function_name):
    # Instantiate the lsp client
    try:
        client = LSPWebSocketClient(URI)
        await client.connect()

        if not os.path.exists(filename):
            print("File does not exist.")
            sys.exit(1)
        if function_name:
            # handle function
            context = await get_function_context(client, filename, function_name)
        else:
            print("Function name not provided.")
            # handle whole file
        # await client.send_message(
        #     {
        #         "jsonrpc": "2.0",
        #         "id": 2,
        #         "method": "textDocument/typeDefinition",
        #         "params": {
        #             "textDocument": {
        #                 "uri": "file:///Users/morgangriffiths/code/code_context/tests/sample.py"
        #             },
        #             "position": {"line": 1, "character": 14},
        #         },
        #     }
        # )
        # response = await client.receive_message()
        # print("response", response)
    finally:
        await client.close()


if __name__ == "__main__":
    """Usage: python lsp_client.py <filename>::<function_name>"""
    import sys

    user_input = sys.argv[1]
    filename, function_name = user_input.split("::")
    asyncio.run(main(filename, function_name))
