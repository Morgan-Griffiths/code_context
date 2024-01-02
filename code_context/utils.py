from enum import Enum
from functools import lru_cache
import json
from pydantic import BaseModel


@lru_cache(maxsize=100)
def read_file_uri(file_uri: str) -> str:
    file_name = file_uri.replace("file://", "")
    with open(file_name) as f:
        file_content = f.read()
    return file_content


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Enum):
            return o.value  # Convert Enum to its value
        if isinstance(o, BaseModel):
            return o.model_dump(by_alias=True)
        return super().default(o)
