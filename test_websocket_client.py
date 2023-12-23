# import pytest
# from lsp_client import (
#     LSPWebSocketClient,
# )

# URI = "ws://0.0.0.0:2087"


# @pytest.mark.asyncio
# async def test_initialization():
#     client = LSPWebSocketClient(URI)
#     await client.connect()
#     response = await client.initialize()
#     assert response == {
#         "id": 1,
#         "jsonrpc": "2.0",
#         "result": {
#             "capabilities": {
#                 "positionEncoding": "utf-16",
#                 "textDocumentSync": {"openClose": True, "change": 2, "save": True},
#                 "completionProvider": {
#                     "triggerCharacters": [".", "'", '"'],
#                     "resolveProvider": True,
#                 },
#                 "hoverProvider": True,
#                 "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
#                 "definitionProvider": True,
#                 "typeDefinitionProvider": {},
#                 "referencesProvider": True,
#                 "documentHighlightProvider": True,
#                 "documentSymbolProvider": True,
#                 "codeActionProvider": {
#                     "codeActionKinds": ["refactor.inline", "refactor.extract"]
#                 },
#                 "workspaceSymbolProvider": {"resolveProvider": False},
#                 "renameProvider": True,
#                 "executeCommandProvider": {"commands": []},
#                 "workspace": {
#                     "workspaceFolders": {
#                         "supported": True,
#                         "changeNotifications": True,
#                     },
#                     "fileOperations": {},
#                 },
#             },
#             "serverInfo": {"name": "jedi-language-server", "version": "0.19.1"},
#         },
#     }
#     await client.close()


# @pytest.mark.asyncio
# async def test_send_message():
#     client = LSPWebSocketClient(URI)
#     await client.connect()
#     response = await client.initialize()
#     await client.send_message(
#         {
#             "jsonrpc": "2.0",
#             "id": 2,
#             "method": "textDocument/typeDefinition",
#             "params": {
#                 "textDocument": {
#                     "uri": "file:///Users/morgangriffiths/code/code_context/tests/sample.py"
#                 },
#                 "position": {"line": 1, "character": 14},
#             },
#         }
#     )
#     response = await client.receive_message()
#     assert response == {
#         "id": 2,
#         "jsonrpc": "2.0",
#         "result": [
#             {
#                 "uri": "file:///Users/morgangriffiths/code/code_context/tests/sample.py",
#                 "range": {
#                     "start": {"line": 1, "character": 4},
#                     "end": {"line": 1, "character": 17},
#                 },
#             }
#         ],
#     }
#     await client.close()
