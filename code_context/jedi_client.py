import asyncio
from contextlib import asynccontextmanager
import json
import subprocess
import sys
from typing import Optional
import websockets
import os


class LanguageServerClient:
    def __init__(self, root_dir: Optional[str]):
        self.jedi_server_process = None
        self.root_dir = (
            root_dir
            if root_dir
            else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        print(f"Running jedi client in {self.root_dir}")

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
                    "rootUri": f"file://{self.root_dir}",
                    "initializationOptions": {},
                },
            }
            await websocket.send(json.dumps(init_message))
            return json.loads(await websocket.recv())

    async def close(self):
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


async def run_jedi(root_dir):
    lsp = LanguageServerClient(root_dir)
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
