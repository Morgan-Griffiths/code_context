import ast
import asyncio
from typing import Optional
import websockets
import json
import os
import sys
import uuid
from code_context.response_types import (
    DocumentSymbol,
    FindReferencesResponse,
    DefinitionResponse,
    GoToDeclarationResponse,
    GoToImplementationResponse,
    NodeInfo,
    TypeDefinitionResponse,
    TypeDefinitionResponse,
    DocumentSymbolResponse,
    ReferenceContext,
    ReferenceParams,
    TextDocument,
    Position,
    VisitedNode,
)

from ast_parsing import (
    extract_code_segment,
    find_all_method_and_function_calls,
    find_function_or_class_range,
    filter_out_builtins_from_locations,
    find_node_at_position,
    find_top_level_definitions,
)
from code_context.utils import read_file_uri, EnhancedJSONEncoder

BREAK_LINE = "\n------------------------------------------------"  # two tokens


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
        return GoToDeclarationResponse.model_validate(response)

    async def get_type_definition(
        self, text_document: TextDocument, position: Position
    ):
        response = await self.send_request(
            "textDocument/typeDefinition",
            {"textDocument": text_document, "position": position},
        )
        return TypeDefinitionResponse.model_validate(response)

    async def go_to_implementation(
        self, text_document: TextDocument, position: Position
    ):
        response = await self.send_request(
            "textDocument/implementation",
            {"textDocument": text_document, "position": position},
        )
        return GoToImplementationResponse.model_validate(response)

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
        return FindReferencesResponse.model_validate(response)

    async def get_document_symbol(
        self, filename: str
    ) -> Optional[list[DocumentSymbol]]:
        text_document = TextDocument(uri=f"file://{filename}")
        response = await self.send_request(
            "textDocument/documentSymbol",
            {"textDocument": text_document},
        )
        return DocumentSymbolResponse.model_validate(response).result

    async def get_definition(
        self, text_document: TextDocument, position: Position
    ) -> DefinitionResponse:
        response = await self.send_request(
            "textDocument/definition",
            {"textDocument": text_document, "position": position},
        )
        return DefinitionResponse.model_validate(response)

    async def get_completion(self, text_document: TextDocument, position: Position):
        response = await self.send_request(
            "textDocument/completion",
            {"textDocument": text_document, "position": position},
        )
        return response


async def get_function_context(
    client: LSPWebSocketClient,
    function_or_class_names: list[NodeInfo],
    visited_nodes: set[VisitedNode],
) -> list[NodeInfo]:
    """Given a file and a function or class name, return all the function calls inside of that function or class. Filters for builtins and duplicates."""
    calls: set[VisitedNode] = set()
    for node_info in function_or_class_names:
        fcalls = find_all_method_and_function_calls(node_info)
        calls.update(fcalls)
    # look up all the call definitions and find the relevant nodes.
    type_definitions: set[NodeInfo] = set()
    for call in calls:
        definition = await client.get_type_definition(
            TextDocument(uri=call.uri),
            Position(line=call.line, character=call.character),
        )
        if definition.result:
            for obj_def in definition.result:
                node = find_node_at_position(
                    read_file_uri(obj_def.uri),
                    obj_def.range.start.line,
                    call.name,
                )
                if isinstance(node, ast.Assign):
                    print("found assign")
                    print(node.targets[0].id)
                    print(node.value, type(node.value))
                    node = None  # node.value

                if node is not None:
                    vnode = VisitedNode(
                        name=node.name,
                        line=node.lineno,
                        character=node.col_offset,
                        uri=obj_def.uri,
                    )
                    if vnode not in visited_nodes:
                        type_definitions.add(NodeInfo(uri=obj_def.uri, node=node))
                        visited_nodes.add(vnode)
    filtered_type_definitions = filter_out_builtins_from_locations(type_definitions)
    return filtered_type_definitions


async def get_depth_n_code_context(
    client: LSPWebSocketClient,
    function_or_class_names: list[NodeInfo],
    depth: int,
):
    # record the target nodes as visited
    visited_nodes: set[VisitedNode] = {
        VisitedNode(
            name=n.node.name, uri=n.uri, line=n.node.lineno, character=n.node.col_offset
        )
        for n in function_or_class_names
    }
    # add target nodes to call list
    function_calls: list[NodeInfo] = function_or_class_names
    # Step 1: find all the calls inside the function(s).
    inner_function_calls = await get_function_context(
        client, function_or_class_names, visited_nodes
    )
    function_calls.extend(inner_function_calls)
    # Step 2: (Optional) recursively find all the sub-function calls.
    for _ in range(depth - 1):
        depth_n_function_calls = []
        for node_info in function_calls:
            inner_function_calls = await get_function_context(
                client,
                [node_info],
                visited_nodes,
            )
            depth_n_function_calls.extend(inner_function_calls)
        function_calls.extend(depth_n_function_calls)
    # Step 3: Given all the nodes and file paths, copy the relevant text.

    code_context = []
    for node_info in function_calls:
        code_snippet = extract_code_segment(
            read_file_uri(node_info.uri), node_info.node
        )
        code_context.append(node_info.uri + "\n" + code_snippet + BREAK_LINE)

    return code_context


async def get_file_context(client: LSPWebSocketClient, filename: str, depth: int):
    # Step 1: Find all the functions and classes in the file.
    top_level_definitions = find_top_level_definitions(filename)
    # Step 2: Iterate through all the functions and classes. Find external references.
    return await get_depth_n_code_context(client, top_level_definitions, depth=depth)


URI = "ws://0.0.0.0:2087"


async def main(filename, function_or_class_name, depth):
    try:
        # Instantiate the lsp client
        client = LSPWebSocketClient(URI)
        await client.connect()

        if not os.path.exists(filename):
            print("File does not exist.")
            sys.exit(1)
        if function_or_class_name:
            # Initial setup: Find function position, etc.
            node_info = find_function_or_class_range(filename, function_or_class_name)
            if node_info is None:
                print("Function or class not found in the file.")
                sys.exit(1)

            context = await get_depth_n_code_context(client, [node_info], depth=depth)
        else:
            # Get context for all the functions and classes in the file
            context = await get_file_context(client, filename, depth=depth)
        context = "\n\n".join(context)
        print(context)
    finally:
        await client.close()


if __name__ == "__main__":
    """Usage: python lsp_client.py <filename>::<function_or_class_name>"""
    import sys

    user_input = sys.argv[1]
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    if "::" in user_input:
        filename, function_or_class_name = user_input.split("::")
    else:
        filename = user_input
        function_or_class_name = None

    asyncio.run(main(filename, function_or_class_name, depth))
