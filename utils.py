def read_file_uri(file_uri):
    file_name = file_uri.replace("file://", "")
    with open(file_name) as f:
        file_content = f.read()
    return file_content
