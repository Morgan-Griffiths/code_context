# Code Context Extractor

This is a tool that leverages LSP and AST parsing to extract relevant code snippets given a file and a function name. It is intended to be used with GPT.

## Usage

1. Start the jedi client. Optionally add the root directory of the project you want to analyze as an argument. Otherwise it will point to the current directory.

`python jedi_client.py <root_dir>`

2. Query the lsp client

Get the code context for an entire file
`python lsp_client.py <file_path>`

Get the code context for a function
`python lsp_client.py <file_path>::<function_name>`

This will return a concatenated string of all relevant code snippets. This can be saved to file or piped to another function.

3. Optionally

make an alias for the lsp client `alias lsp="python lsp_client.py"`

Get the code context for a function and add a prompt, then pipe it to GPT.
`(lsp <file_path>::<function_name> && <prompt>) | <function>`

Or save the output to file.
`(lsp <file_path>::<function_name> && <prompt>) > <file>`

## Example

Example:
`(lsp test.py::test && "add another test") | gpt`
