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
    FindReferencesResponse,
    DefinitionResponse,
    GoToDeclarationResponse,
    GoToImplementationResponse,
    TypeDefinitionResponse,
    TypeDefinitionResponse,
    DocumentSymbolResponse,
    ReferenceContext,
    ReferenceParams,
    TextDocument,
    Position,
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

    async def initialize(self):
        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "capabilities": {
                    # "textDocument": {
                    #     "callHierarchy": {"dynamicRegistration": True},
                    #     # Include other capabilities as needed
                    # },
                    # Other client capabilities
                },
                "workspaceFolders": None,
                "rootUri": "file:///Users/morgangriffiths/code/code_context/tests",
                "initializationOptions": {},
            },
        }
        await self.send_message(init_message)
        return await self.receive_message()

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

    async def find_references(self, text_document: TextDocument, position: Position):
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

    async def get_document_symbol(self, filename: str) -> DocumentSymbolResponse:
        text_document = TextDocument(uri=f"file://{filename}")
        response = await self.send_request(
            "textDocument/documentSymbol",
            {"textDocument": text_document},
        )
        return DocumentSymbolResponse(**response)

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


async def get_function_context(
    client: LSPWebSocketClient, filename: str, function_name: str
):
    # Initial setup: Find function position, etc.
    text_document = TextDocument(uri=f"file://{filename}")
    position = find_function_position(filename, function_name)
    print("text_document", text_document)
    print("position", position)
    if position is None:
        print("Function not found in the file.")
        sys.exit(1)
    function_def = await client.get_definition(text_document, position)
    first_definition = function_def.result[0]
    print("first_definition", first_definition)

    # Step 1: get symbols within the function
    symbols_in_scope = await client.get_document_symbol(filename)
    # print("symbols", symbols_in_scope)
    all_type_files = set()
    all_reference_files = set()
    for symbol in symbols_in_scope.result:
        # print("symbol", symbol)
        type_info = await client.get_type_definition(
            text_document, symbol.location.range.start
        )
        if type_info.result:
            all_type_files.add(type_info.result[0].uri)
        references = await client.find_references(
            text_document, symbol.location.range.start
        )
        if references.result:
            all_reference_files.update({ref.uri for ref in references.result})

    print("equal", all_type_files == all_reference_files)
    print(all_type_files - all_reference_files)
    print(all_reference_files - all_type_files)
    # print("all_type_files", all_type_files)
    # print("all_reference_files", all_reference_files)

    # Step 2: Find external references
    external_references = await client.find_references(text_document, position)
    print("external_references", external_references)
    # filter out references in the same file
    external_references = [
        ref for ref in external_references.result if ref.uri != f"file://{filename}"
    ]
    print("external_references", external_references)
    # Step 3: Extract relevant code blocks
    # ...

    # Step 4: Combine the extracted code into a single context block
    # ...
    combined_context = ""
    return combined_context


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
    # LSP_server = LanguageServer()
    # await LSP_server.initialize()
    # await LSP_server.close()
    # Close the input/output streams

    # Instantiate the lsp client
    client = LSPWebSocketClient(URI)
    await client.connect()

    # response = await client.initialize()
    # print("init response", response)

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
    await client.close()


if __name__ == "__main__":
    """Usage: python lsp_client.py <filename>::<function_name>"""
    import sys

    user_input = sys.argv[1]
    filename, function_name = user_input.split("::")
    asyncio.run(main(filename, function_name))
