import asyncio
import os
import sys


import click
from code_context.lsp_client import call_lsp
from code_context.jedi_client import run_jedi


@click.group()
def cli():
    pass


@cli.command()
@click.argument("file_and_function", required=True)
@click.argument("depth", default=1, type=int)
def lsp(file_and_function, depth):
    """
    Run the LSP client on a given file and optional function.
    Usage: lsp <file_name>::<function_name> <depth>
    """
    if "::" in file_and_function:
        file_name, function_name = file_and_function.split("::")
    else:
        file_name = file_and_function
        function_name = None

    asyncio.run(call_lsp(file_name, function_name, depth))


@cli.command()
@click.argument(
    "root_dir",
    type=click.Path(exists=True),
)
def start_jedi(root_dir):
    """
    Start the Jedi client.
    """
    print(sys.argv)
    root_dir = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(run_jedi(root_dir))


if __name__ == "__main__":
    cli()
