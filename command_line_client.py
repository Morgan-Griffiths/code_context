from lsp_client import LSPWebSocketClient
import asyncio

URI = "ws://0.0.0.0:2087"

""" usage (ls ; echo "db") | grep "db" """

async def main():
    client = LSPWebSocketClient(URI)
    await client.connect()
    response = await client.initialize()
    try:
        print("init response", response)
        await client.send_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/typeDefinition",
                "params": {
                    "textDocument": {
                        "uri": "file:///Users/morgangriffiths/code/code_context/tests/sample.py"
                    },
                    "position": {"line": 1, "character": 14},
                },
            }
        )
        response = await client.receive_message()

if __name__ == "__main__":
    asyncio.run(main())