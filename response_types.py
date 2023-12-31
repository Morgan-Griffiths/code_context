from typing import List, Optional, Any, Union
from pydantic import BaseModel, Field
from enum import Enum


class HashableBaseModel(BaseModel):
    """Base class for pydantic models that can be hashed and compared"""

    def __hash__(self):
        return hash((self.__class__,) + tuple(self.__fields__.values()))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            for field in self.__fields__:  # type: ignore
                if getattr(self, field) != getattr(other, field):
                    return False
            return True
        return False


class Position(HashableBaseModel):
    line: int
    character: int


class Range(HashableBaseModel):
    start: Position
    end: Position


##########################################
######### AST PARSING TYPES ##############
##########################################


class VisitedNode(HashableBaseModel):
    uri: str
    line: int
    character: int
    name: str


class NodeInfo(HashableBaseModel):
    node: Any
    uri: str


class ImportInfo(HashableBaseModel):
    file_path: str
    module_name: Optional[str]
    line: int
    character: int


class CallInfo(HashableBaseModel):
    function_name: str
    line: int
    character: int


class ObjectTypes(Enum):
    FUNCTION = "Function"
    ASYNC_FUNCTION = "Async Function"
    CLASS = "Class"


##########################################
######### LSP CLIENT TYPES ###############
##########################################


class SymbolKind(Enum):
    File = 1
    Module = 2
    Namespace = 3
    Package = 4
    Class = 5
    Method = 6
    Property = 7
    Field = 8
    Constructor = 9
    Enum = 10
    Interface = 11
    Function = 12
    Variable = 13
    Constant = 14
    String = 15
    Number = 16
    Boolean = 17
    Array = 18
    Object = 19
    Key = 20
    Null = 21
    EnumMember = 22
    Struct = 23
    Event = 24
    Operator = 25
    TypeParameter = 26


class Location(HashableBaseModel):
    uri: str
    range: Range


class SymbolTag(BaseModel):
    value: int


class CallHierarchyItem(BaseModel):
    name: str
    kind: SymbolKind
    tags: Optional[List[SymbolTag]]
    detail: Optional[str]
    uri: str
    range: Range
    selectionRange: Range
    data: Optional[Any]


class TextDocument(BaseModel):
    uri: str


class DefinitionResponse(BaseModel):
    result: Optional[List[Union[Location, Range]]]


class GoToDeclarationResponse(BaseModel):
    result: Optional[List[Location]]


class GoToDefinitionResponse(BaseModel):
    result: Optional[List[Location]]


class PrepareCallHierarchyResponse(BaseModel):
    result: Optional[List[CallHierarchyItem]]


class TypeDefinitionResponse(BaseModel):
    result: Optional[List[Location]]


class CallHierarchyIncomingCall(BaseModel):
    from_: CallHierarchyItem = Field(..., alias="from")
    fromRanges: List[Range]


class CallHierarchyIncomingCallsResponse(BaseModel):
    result: Optional[List[CallHierarchyIncomingCall]]


class CallHierarchyOutgoingCall(BaseModel):
    to: CallHierarchyItem
    fromRanges: List[Range]


class CallHierarchyOutgoingCallsResponse(BaseModel):
    result: Optional[List[CallHierarchyOutgoingCall]]


class TypeHierarchyItem(CallHierarchyItem):
    ...


class TypeHierarchyResponse(BaseModel):
    result: Optional[List[TypeHierarchyItem]]


class ReferenceContext(BaseModel):
    include_declaration: bool = Field(..., alias="includeDeclaration")


class ReferenceParams(BaseModel):
    text_document: TextDocument = Field(..., alias="textDocument")
    position: Position
    context: ReferenceContext

    class Config:
        allow_population_by_field_name = True


class GoToImplementationResponse(BaseModel):
    result: Optional[List[Location]]


class FindReferencesResponse(BaseModel):
    result: Optional[List[Location]]


class DocumentSymbol(BaseModel):
    location: Location
    name: str
    kind: SymbolKind
    containerName: Optional[str]


class DocumentSymbolResponse(BaseModel):
    result: Optional[List[DocumentSymbol]]
