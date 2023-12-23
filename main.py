import sys

from jedi_language_server import LanguageServerClient
from lsp_client import LSPWebSocketClient


async def main():
    async with LanguageServerClient() as lsp:
        await lsp.check_types()
        await lsp.check_more_types()


if __name__ == "__main__":
    ...
