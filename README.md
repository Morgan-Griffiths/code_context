# Code Context Extractor for python

This is a tool that leverages LSP and AST parsing to extract relevant python code snippets given a file and optionally a function name in that file. It is intended to be used with ChatGPT.

## Current limitations

Only parses classes and functions. Does not parse assignments, or non-function class attributes. Only parses content inside functions.

## Output Format

The output is a concatenated string of all relevant code snippets. The code snippets are ordered by depth, starting from the bottom of the file at depth 0 - given function(s) return all called functions and classes that are defined outside the function. This is followed by depth N-1 - all functions and classes that are defined inside the functions returned in depth 1. And so on up to arbitrary depth. The ordering is reversed so that GPT see's the children function definitions prior to the parent function definition.

The output looks like the following:

```
<file_uri>
<function_or_class>
------------------------------------------------

<file_uri>
<function_or_class>
------------------------------------------------

...
```

## Usage

1. Start the jedi client. Optionally add the root directory of the project you want to analyze as an argument. Otherwise it will point to the current directory.

`python jedi_client.py <root_dir>`

2. Query the lsp client

Get the code context for an entire file
`python lsp_client.py <file_path>`

Get the code context for a function
`python lsp_client.py <file_path>::<function_name>`

This will return a concatenated string of all relevant code snippets. This can be saved to file or piped to another function.

Increase the depth for more context (default is 1)
`python lsp_client.py <file_path>::<function_name> <depth>`

3. Optionally

make an alias for the lsp client `alias lsp="python lsp_client.py"`

4. Composition

Get the code context for a function and add a prompt, then pipe it to GPT.
`(lsp <file_path>::<function_name> && <prompt>) | <function>`

Or save the output to file.
`lsp <file_path>::<function_name> > <file>`

5. Pipe output to GPT via the commandline (requires a GPT commandline tool such as https://github.com/Morgan-Griffiths/commandline_gpt)

`(lsp path_to_python_fie.py && echo "Can you explain what this code does?") | g`
