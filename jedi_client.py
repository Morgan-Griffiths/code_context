import asyncio
from contextlib import asynccontextmanager
import json
import subprocess
import websockets
import os


class LanguageServerClient:
    def __init__(self):
        self.jedi_server_process = None

    async def initialize(self):
        self.jedi_server_process = subprocess.Popen(
            ["jedi-language-server", "--ws"],
        )

        # Wait for the server to start
        await asyncio.sleep(1)
        self.uri = "ws://localhost:2087"
        async with websockets.connect(self.uri) as websocket:
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "capabilities": {},
                    "workspaceFolders": None,
                    "rootUri": "file:///Users/morgangriffiths/code/code_context/tests",
                    "initializationOptions": {},
                },
            }
            await websocket.send(json.dumps(init_message))
            return json.loads(await websocket.recv())

    async def close(self):
        # await self.shutdown_language_server()
        # Terminate the process
        self.jedi_server_process.terminate()

        # Wait for the process to terminate
        self.jedi_server_process.wait()


# language server constructor


@asynccontextmanager
async def lsp_server():
    lsp = LanguageServerClient()
    try:
        await lsp.initialize()
        yield lsp
    finally:
        await lsp.close()


async def main():
    lsp = LanguageServerClient()
    try:
        await lsp.initialize()
        # Create an event that will be set when the program should terminate.
        stop_event = asyncio.Event()

        try:
            # Wait for the event to be set.
            await stop_event.wait()
        except KeyboardInterrupt:
            # Set the event to exit the loop upon KeyboardInterrupt.
            stop_event.set()

        # Perform any necessary cleanup.
        await lsp.close()

    except Exception as e:
        # Handle any exceptions during initialization or runtime.
        print(f"An error occurred: {e}")
        await lsp.close()


if __name__ == "__main__":
    asyncio.run(main())
