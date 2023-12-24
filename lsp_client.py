import asyncio
from typing import Optional
import websockets
import json
import os
import sys
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
    extract_code_segment,
    find_all_method_and_function_calls,
    find_function_range,
    filter_locations,
    find_node_at_position,
)
from utils import read_file_uri, EnhancedJSONEncoder


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


async def get_function_context(
    client: LSPWebSocketClient, filename: str, function_name: str, depth=1
):
    with open(filename, "r") as file:
        file_content = file.read()
    # Initial setup: Find function position, etc.
    text_document = TextDocument(uri=f"file://{filename}")
    function_range = find_function_range(filename, function_name)
    if function_range is None:
        print("Function not found in the file.")
        sys.exit(1)

    # Step 1: find all the calls inside the function.
    calls = find_all_method_and_function_calls(file_content, function_name)

    # Step 2: look up all the call definitions.
    type_definitions = set()
    for call in calls:
        definition = await client.get_type_definition(
            text_document,
            Position(line=call.line, character=call.character),
        )
        if definition.result:
            for obj_def in definition.result:
                type_definitions.add(obj_def)
    # filter out builtins
    filtered_type_definitions = filter_locations(type_definitions)
    # print("filtered_type_definitions", filtered_type_definitions)
    nodes = [
        find_node_at_position(read_file_uri(def_.uri), def_.range.start.line)
        for def_ in filtered_type_definitions
    ]

    # Step 3: Given all the nodes, copy the relevant text.
    code_context = []
    for node, def_ in zip(nodes, filtered_type_definitions):
        code_snippet = extract_code_segment(read_file_uri(def_.uri), node)
        # print(f"{def_}. code_snippet {code_snippet}")
        code_context.append(
            def_.uri + "\n------------------" + code_snippet + "------------------"
        )

    return code_context


URI = "ws://0.0.0.0:2087"


async def main(filename, function_name):
    try:
        # Instantiate the lsp client
        client = LSPWebSocketClient(URI)
        await client.connect()

        if not os.path.exists(filename):
            print("File does not exist.")
            sys.exit(1)
        if function_name:
            context = await get_function_context(client, filename, function_name)
            # save to file
            with open("code_context.txt", "w") as file:
                file.write("\n\n".join(context))

        else:
            print("Function name not provided.")
    finally:
        await client.close()


if __name__ == "__main__":
    """Usage: python lsp_client.py <filename>::<function_name>"""
    import sys

    user_input = sys.argv[1]
    filename, function_name = user_input.split("::")
    asyncio.run(main(filename, function_name))

    # Testing
    # filename = (
    #     "/Users/morgangriffiths/code/openai/torchflow/torchflow/layouts/pipe_layout.py"
    # )
    # node = find_node_at_position(filename, 723)
    # print(f"{node}, {dir(node)}, {node.name}")
