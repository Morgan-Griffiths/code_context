import subprocess
import asyncio
import socket
import pytest

from jedi_client import LanguageServerClient


async def check_server(port):
    try:
        # Try to create a socket connection to the server
        with socket.create_connection(("localhost", port), timeout=1):
            return True
    except (ConnectionRefusedError, socket.timeout):
        return False


@pytest.mark.asyncio
async def test_lsp_server():
    LSP_server = LanguageServerClient()
    init_response = await LSP_server.initialize()
    await asyncio.sleep(1)
    assert await check_server(2087)
    await LSP_server.close()

    # assert no server is running on 2087
    assert await check_server(2087) is False


if __name__ == "__main__":
    asyncio.run(test_lsp_server())
