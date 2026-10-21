from typing import Literal, NotRequired, Required

from typing_extensions import TypedDict

type SupportedProgrammingLanguage = Literal["java", "python", "c++"]

type AstId = int
type ScopeId = int
type BytePosition = list[int]

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue] | Node
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]

# Типы постоянно добавляются и расширяются, поэтому решено аннотировать его строкой
type NodeType = str
type NodeField = str
type TreeField = Literal["type", "unique_hash", "labels", "root_node"]
type TokenField = str
type MapField = Literal[
    "type",
    "origin",
    "source_code",
    "language",
    "byte_positions",
    "render_scope_table",
    "origin_scope_table",
    "metrics",
    "project_root_path",
    "project_file_rel_path",
]


class Label(TypedDict, total=False):
    id: Required[int]
    stealth: bool
    attr: JsonValue


class Node(TypedDict, extra_items=JsonValue):
    """Общие поля узла и произвольные поля, зависящие от ``type``."""

    id: AstId
    type: NodeType
    unique_hash: NotRequired[int]
    labels: NotRequired[list[Label]]
    jump_label: NotRequired["Node"]
    resolved_declaration_id: NotRequired[AstId]


type JSON = JsonObject | Node


class PartialNode(TypedDict, extra_items=JsonValue):
    """Частичное представление узла для сопоставления с AST-правилами."""

    type: NodeType
    id: NotRequired[AstId]


type NodeQueryFormat = Node | PartialNode


class MeaningTree(TypedDict):
    type: Literal["meaning_tree"]
    unique_hash: int
    root_node: Node
    labels: NotRequired[list[Label]]


type EstimateValue = bool | int | float | str | None


class ExpressionValueEstimate(TypedDict):
    exact_value: NotRequired[EstimateValue]
    possible_values: list[bool | int | float | str]
    reliable: bool


class ScopeNodeRef(TypedDict, total=False):
    node_type: NodeType
    ast_id: AstId
    identifier: str | None
    parent_declaration_ast_id: AstId
    declaration_ast_id: AstId
    repr_name: str
    is_const: bool
    is_safe_reference: bool
    value_estimate: ExpressionValueEstimate


class ScopeImportRef(ScopeNodeRef, total=False):
    module_name: str
    members: list[str]
    modules: list[str]
    file_name: str
    is_static: bool
    all_content_include: bool


class NamedScopeNode(TypedDict, total=False):
    name: str | None
    declaration: Required[ScopeNodeRef]


class ScopeDefinition(TypedDict):
    declaration: ScopeNodeRef
    definition: ScopeNodeRef


type OverloadKind = Literal["function", "method", "constructor"]


class OverloadGroup(TypedDict, total=False):
    scope_id: Required[ScopeId]
    name: Required[str]
    kind: Required[OverloadKind]
    owner: Node | None
    declarations: Required[list[ScopeNodeRef]]


class ScopeSymbols(TypedDict):
    declarations: list[NamedScopeNode]
    definitions: list[ScopeDefinition]
    overload_groups: list[OverloadGroup]


class NamedTypeRef(TypedDict, total=False):
    name: str | None
    type_ref: Required[Node]


class TypeDeclarationRef(TypedDict):
    type_ref: Node
    declaration: ScopeNodeRef


class TypeHierarchyEntry(TypedDict):
    type_ref: Node
    parents: list[Node]


class ScopeTypes(TypedDict):
    declared_types: list[NamedTypeRef]
    type_declarations: list[TypeDeclarationRef]
    hierarchy: list[TypeHierarchyEntry]


class ScopeImports(TypedDict):
    items: list[ScopeImportRef]


class ScopeVariable(TypedDict, total=False):
    name: str | None
    type_ref: Required[Node]
    declaration: ScopeNodeRef


class ScopeRebind(TypedDict, total=False):
    name: str | None
    scope_id: Required[ScopeId]


class ScopeEntry(TypedDict, total=False):
    id: Required[ScopeId]
    parent_id: ScopeId | None
    owner_ast_id: AstId | None
    variables: Required[list[ScopeVariable]]
    declarations: Required[list[NamedScopeNode]]
    declared_types: Required[list[NamedTypeRef]]
    type_declarations: Required[list[TypeDeclarationRef]]
    rebinds: Required[list[ScopeRebind]]


type AssignmentBinding = Literal["ENCLOSING", "LOCAL"]


class ScopeTable(TypedDict):
    type: Literal["scope_table"]
    current_scope_id: ScopeId
    assignment_binding: AssignmentBinding
    symbols: ScopeSymbols
    types: ScopeTypes
    imports: ScopeImports
    scopes: list[ScopeEntry]


class SourceMap(TypedDict):
    type: Literal["source_map"]
    origin: MeaningTree | Node
    source_code: str
    language: SupportedProgrammingLanguage
    byte_positions: dict[str, BytePosition]
    render_scope_table: ScopeTable
    origin_scope_table: NotRequired[ScopeTable]
    metrics: dict[str, int | float]
    project_root_path: NotRequired[str]
    project_file_rel_path: NotRequired[str]


type TokenType = Literal[
    "operator",
    "const",
    "callable_identifier",
    "identifier",
    "keyword",
    "cast",
    "comment",
    "opening_brace",
    "closing_brace",
    "subscript_opening_brace",
    "subscript_closing_brace",
    "call_opening_brace",
    "call_closing_brace",
    "compound_opening_brace",
    "compound_closing_brace",
    "initializer_list_opening_brace",
    "initializer_list_closing_brace",
    "statement_token",
    "separator",
    "comma",
    "unknown",
]
type OperatorAssociativity = Literal["left", "right", "non_assoc"]
type OperatorArity = Literal["unary", "binary", "ternary"]
type OperandPosition = Literal["left", "center", "right"]
type OperatorType = Literal[
    "and", "or", "method_call", "new_array", "new", "conditional", "other"
]


class Token(TypedDict, total=False):
    type: Required[str]
    is_pseudo: Required[bool]
    metadata: JsonValue
    has_newlines: bool
    token_position: int
    token_values: list[str]
    precedence: int
    associativity: OperatorAssociativity
    arity: OperatorArity
    is_strict_order: bool
    first_evaluated_operand: OperandPosition | None
    optype_metadata: OperatorType | None
    operand_of: AstId | None
    operand_pos: OperandPosition | None
    token_type: Required[TokenType]
    value: Required[str]
    id: Required[AstId]
    assigned_label: Required[str]
    belongs_to: AstId | None
    byte_pos: BytePosition | None


class TokenList(TypedDict):
    type: Literal["tokens"]
    items: list[Token]
