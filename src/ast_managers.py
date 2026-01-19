from calendar import c
from collections.abc import Callable, Generator, Iterable, Iterator
from dataclasses import dataclass
from functools import wraps
from typing import Any, Literal, Protocol, runtime_checkable

from src.coderenderer.entities import RendererEntity, Token
from src.meaning_tree import node_hierarchy
from src.types import JSON, JsonObject, MeaningTree, Node, SourceMap, TokenList
from src.types import Token as TokenJson

type Declaration = tuple[str, int]
type TopLevelKey = Literal["functions", "classes", "globals"]
type InnerLevelKey = Literal["methods", "fields", "classes"]
type DeclarationElement = Declaration | tuple[Declaration, dict[InnerLevelKey, list["DeclarationElement"]]]
type DeclarationContainer = dict[TopLevelKey, list[DeclarationElement]]

node_type_hierarchy: JSON | None = None


@runtime_checkable
class Observation(Protocol):
    """
    Протокол для декорированных функций наблюдения.
    Имеет атрибуты id и accepts_node_only.
    """
    id: str
    accepts_node_only: bool

    def __call__(self, cur: "TokenCursor | NodePathElement") -> bool | None: ...


@runtime_checkable
class Injection(Protocol):
    """
    Протокол для инъекций.
    Имеет атрибут conditions (список/кортеж наблюдений) и возвращает bool (сработал или нет).
    """
    conditions: tuple[Observation, ...]

    def __call__(self, point: "InjectionPoint") -> bool: ...


@dataclass
class NodePathElement:
    parent: "NodePathElement | None"
    ast_id: int
    ast_type: str
    field_name: str | None
    field_type: Literal["plain", "map", "collection"]
    container_field_id: int | str | None

    def instanceof(self, match_type: str) -> bool:
        # instanceof check
        if self.ast_type == match_type:
            return True
        parents = ASTNodeAnalyzer.get_node_type_parents(self.ast_type)
        return match_type in (parents or [])

    def get(self, analyzer: "ASTNodeAnalyzer") -> Node | None:
        return analyzer.get(self)


class ASTNodeAnalyzer:
    def __init__(self, root: MeaningTree | Node):
        self._root = root
        self._cache: dict[int, tuple[NodePathElement, Node]] = {}
        self._init_hierarchy()

    @property
    def root(self) -> MeaningTree | Node:
        return self._root

    def properties(self, root: Node | NodePathElement | int | None = None) -> dict[str, Any]:
        if root is None:
            src = self.root
        elif isinstance(root, (int, NodePathElement)):
            src = self.get(root) or {}

        labels: dict[str, Any] = {}
        raw_labels: list[dict[str, Any]] = src.get("labels", []) # type: ignore
        if isinstance(raw_labels, list):
            for label in raw_labels:
                label_id = label.get("id", None)
                if label_id == 0:
                    labels["value"] = label.get("attr")
                elif label_id == 3:
                    match (label.get("attr", "").lower()):
                        case 0:
                            labels["origin_language"] = "c++"
                        case 1:
                            labels["origin_language"] = "python"
                        case 2:
                            labels["origin_language"] = "java"
        return labels

    @staticmethod
    def _init_hierarchy():
        global node_type_hierarchy
        if node_type_hierarchy is None:
            node_type_hierarchy = node_hierarchy()

    def _process(self):
        def traverse(node,
                     prev: NodePathElement | None = None,
                     field: str | None = None,
                     f_id: str | int | None = None) -> NodePathElement | None:
            if isinstance(node, dict) and "id" in node:
                if node["id"] in self._cache and node["type"] != self._cache[node["id"]][1]["type"]:
                    raise ValueError(f"AST ID collision detected for ID {node['id']}, tree is corrupted")

                if node["id"] not in self._cache:
                    node_id = int(node["id"])

                    field_type = "plain"
                    if prev is not None:
                        prev_node = prev.get(self)
                        if prev_node is not None:
                            field_value = prev_node.get(field or "")
                            if isinstance(field_value, dict) and "id" not in field_value:
                                field_type = "map"
                            elif isinstance(field_value, list):
                                field_type = "collection"

                    path_element = NodePathElement(
                        parent=prev,
                        ast_id=node_id,
                        ast_type=node["type"],
                        field_name=field,
                        field_type=field_type,
                        container_field_id=f_id
                    )
                    self._cache[node_id] = (path_element, node)
                    for key, value in node.items():
                        if isinstance(value, (list, dict)):
                            traverse(value, path_element, key)
                    return path_element
                else:
                    return self._cache[int(node["id"])][0]
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    if isinstance(item, (list, dict)):
                        traverse(item, prev, field, i)
            elif isinstance(node, dict) and "id" not in node:
                for key, value in node.items():
                    if isinstance(value, (list, dict)):
                        traverse(value, prev, field, key)

        traverse(self.root.get("root_node", self.root))

    def get_path(self, node_ast_id: int) -> NodePathElement | None:
        return self._cache.get(node_ast_id, (None, None))[0]

    def get(self, node: int | NodePathElement) -> Node | None:
        if isinstance(node, int):
            return self._cache.get(node, (None, None))[1]
        else:
            for _, (path_element, ast_node) in self._cache.items():
                if path_element == node:
                    return ast_node

    def get_parent_of(self, node: int | NodePathElement) -> JSON | None:
        if isinstance(node, int):
            if path := self.get_path(node):
                return path.parent.get(self) if path.parent else None
        else:
            return node.parent.get(self) if node.parent else None

    @classmethod
    def get_node_type_parents(cls, node_type: str) -> list[str] | None:
        cls._init_hierarchy()
        if not node_type_hierarchy:
            return None
        return node_type_hierarchy.get(node_type) # type: ignore

    def instanceof(self, node_id: int, node_type: str) -> bool:
        node = self.get_path(node_id)
        return node.instanceof(node_type) if node else False

    def exists(self, ast_id: int) -> bool:
        return ast_id in self._cache

    def __iter__(self):
        return iter(self._cache.items())


class TokenCursor:
    '''Указатель на токен (индекс равен 0), вокруг него могут быть другие токены (индексы -1, -2... и +1, +2...) в зависимости от lookaround'''
    def __init__(self, owner: "CodeManager", lookaround: int, real_index: int, buf: list[RendererEntity]):
        self._center = lookaround
        self._lookaround = lookaround
        self._buf = buf
        self._owner = owner
        self._real_index = real_index

    def _align(self, index: int) -> int:
        return index + self._center

    def __iter__(self):
        return iter(self._buf)

    def __getitem__(self, offset: int | slice) -> RendererEntity | list[RendererEntity]:
        return self._buf[self._align(offset)] if isinstance(offset, int) \
            else self._buf[self._align(offset.start):self._align(offset.stop)]

    def translate_index(self, offset: int) -> int:
        return self._real_index + offset

    @property
    def max_seek(self) -> int:
        '''Максимальный 'радиус' доступных токенов вокруг текущего'''
        return self._lookaround


class CodeManager:
    def __init__(self, ast: ASTNodeAnalyzer, source_map: SourceMap, tokens: TokenList):
        self._ast = ast
        self._source_map = source_map
        self._tokens: list[Token] = self._remap(tokens) # type: ignore
        self._code = self._source_map.get("source_code", "").replace("\r", "")  # type: ignore
        self._declarations: DeclarationContainer = {
            "functions": [], "classes": [], "globals": []
        }
        self._last_stream: InjectionManager | None = None
        self._process_declarations()

    def _remap(self, tlist: TokenList) -> list[Token]:
        tokens: list[Token] = tlist.get("tokens", []) # type: ignore
        return [Token(
                token.get("id"),
                token.get("value", ""),
                token.get("token_type", ""),
                i,
                self._locate(i, token),
                []
            ) for i, token in enumerate(tokens) if not isinstance(token, Token)]

    def _locate(self, index: int, token: TokenJson) -> NodePathElement | None:
        token_byte_pos: tuple[int, int] = token.get("byte_pos", 0) # type: ignore
        map_byteranges: dict[int, tuple[int, int]] = self._source_map.get(
            "byte_positions", {})  # type: ignore

        candidates: list[tuple[int, tuple[int, int]]] = []
        for ast_id, byte_range in map_byteranges.items():
            start_byte, length = byte_range
            start_token_byte, token_length = token_byte_pos
            if start_byte <= start_token_byte < \
                start_token_byte + token_length < start_byte + length:
                candidates.append((ast_id, (start_byte, length)))
        candidates.sort(key=lambda x: (x[1][0] + x[1][1], x[1][1])) # по уровню вложенности
        if candidates:
            ast_id = candidates[0][0]
            path_element = self._ast.get_path(ast_id)
            if path_element:
                return path_element

    @property
    def token_count(self) -> int:
        return len(self._tokens)

    @property
    def code(self) -> str:
        return self._code

    @property
    def bytes(self) -> bytes:
        return self._code.encode("utf-8")

    @property
    def line_count(self) -> int:
        return self.code.count("\n")

    @property
    def last_processed(self) -> list[RendererEntity] | None:
        return self._last_stream.result() if self._last_stream else None

    def get_token(self, index: int | slice) -> Token | list[Token] | None:
        if isinstance(index, slice):
            if 0 <= index.start < len(self._tokens) \
                and 0 <= (index.stop - 1) < len(self._tokens):
                return self._tokens[index]  # type: ignore
        else:
            if 0 <= index < len(self._tokens):
                return self._tokens[index]
        return None

    def code_piece(self, ast_node_id: int) -> str | None:
        byte_range: tuple[int, int] = self._source_map.get(
            "byte_positions", {}
        ).get(str(ast_node_id))  # type: ignore
        code = self.bytes
        if not byte_range:
            return None
        return code[byte_range[0]:byte_range[0] + byte_range[1]].decode('utf-8')

    def line_number(self, token: int | Token) -> int | None:
        line = 1
        token_index = token.index if isinstance(token, Token) else token
        for i, token in enumerate(self):
            if i == token_index:
                return line
            if "\n" in token.value:
                line += token.value.count("\n")
        return None

    def line_number_range(self, ast_node_id: int) -> tuple[int, int] | None:
        token_start, token_end = self.token_index_range(ast_node_id) or (None, None)
        if token_start is None or token_end is None:
            return None
        start_line = self.line_number(token_start)
        end_line = self.line_number(token_end)
        if start_line is None or end_line is None:
            return None
        return start_line, end_line

    def token_index_range(self, ast_node_id: int) -> tuple[int, int] | None:
        min_i, max_i = self.token_count, 0
        for i, token in enumerate(self):
            if token.ast_node and token.ast_node.ast_id == ast_node_id:
                min_i = min(min_i, i)
                max_i = max(max_i, i)
        if min_i <= max_i:
            return (min_i, max_i)
        return None

    def _process_class_def(self, node: Node, decl: JsonObject,
                           parent: list[DeclarationElement] | None = None):
        content = {"methods": [], "fields": [], "classes": []}
        if parent is None:
            parent = self._declarations["classes"]

        parent.append(
            (
                (str(decl["name"]), int(decl["definitionNodeId"])),  # type: ignore
                content,
            )
        )
        for child in node.get("body", {}).get("statements", []): # type: ignore
            if child["type"] == "method_declaration":
                content["methods"].append(
                    (child["name"], child["definitionNodeId"])
                )
            elif child["type"] == "field_declaration":
                content["fields"].append(
                    (child["name"], child["declarationNodeId"])
                )
            elif child["type"] == "class_declaration":
                self._process_class_def(child, {
                    "name": child["name"],
                    "definitionNodeId": child["id"]
                }, content["classes"])

    def _process_declarations(self):
        for decl in self._source_map.get("declarations", []):  # type: ignore
            if decl["type"] == "function_declaration":
                self._declarations["functions"].append(
                    (str(decl["name"]), int(decl["definitionNodeId"]))
                )
            elif decl["type"] == "class_declaration":
                node = self._ast.get(decl["definitionNodeId"])
                if node:
                    self._process_class_def(node, decl)
                else:
                    raise ValueError(f"Class declaration {decl["name"]} node not found in AST")
            elif decl["type"] == "variable_declaration":
                self._declarations["globals"].append((decl["name"], decl["declarationNodeId"]))

    def __getattr__(self, name):
        # Проксирование к ASTNodeAnalyzer
        try:
            return getattr(self._ast, name) # если нет в текущем объекте только
        except AttributeError:
            raise AttributeError(
                f"{self.__class__.__name__!r} object has no attribute {name!r}"
            ) from None

    @property
    def ast(self) -> ASTNodeAnalyzer:
        return self._ast

    @property
    def source_map(self) -> SourceMap:
        return self._source_map

    def __iter__(self):
        return iter(self._tokens)

    def stream(self, from_: int | None = None, to: int | None = None, step: int = 1, *, lookaround: int = 1) -> Generator[TokenCursor]:
        from_ = from_ if from_ is not None else 0
        to = to if to is not None else self.token_count

        if from_ < 0 or to > self.token_count or from_ >= to:
            raise IndexError("Token stream 'from' index is out of range")
        if to < 1 or to > self.token_count + 1:
            raise IndexError("Token stream 'to' index is out of range")
        if step < 1:
            raise ValueError("Token stream 'step' must be at least 1")

        for i in range(from_, to, step):
            tokens = []
            for j in range(i - lookaround, i + lookaround + 1):
                token = self.get_token(j)
                tokens.append(token if token is not None else {})
            yield TokenCursor(self, lookaround, i, tokens)

    def injection_stream(self,
                         conditions: Iterable[Observation],
                         from_: int | None = None,
                         to: int | None = None,
                         step: int = 1,
                         lookaround: int = 1) -> Generator["InjectionPoint"]:
        self._last_stream = InjectionManager(
            self.stream(from_, to, step, lookaround=lookaround),
            self,
            conditions)
        yield from self._last_stream


class InjectionPoint(TokenCursor):
    def __init__(self, owner: "InjectionManager", lookaround: int,
                 real_index: int,
                 matched_conditions: list[Observation],
                 buf: list[RendererEntity]):
        super().__init__(owner._owner, lookaround, real_index, buf)
        self._injection_owner = owner
        self._matched_conditions = matched_conditions

    @property
    def matched_conditions(self) -> list[Observation]:
        return self._matched_conditions

    def _apply(self) -> list[RendererEntity]:
        '''Применение изменений после завершения итерации'''
        return self._buf

    def push_before(self, *items: RendererEntity):
        self.insert(0, *items)

    def push_after(self, *items: RendererEntity):
        self.insert(1, *items)

    def __setitem__(self, index: int, item: RendererEntity):
        self._buf[self._align(index)] = item

    def remove_after(self, count: int): # в пределах lookaround
        self.remove(1, count)

    def remove_before(self, count: int):  # в пределах lookaround
        self.remove(0, count, rtl=True)

    def flag(self, name: str, value: int | bool | None = None) -> int | bool | None:
        self._owner._flags.setdefault(name, value)
        return self._owner._flags["name"]

    @property
    def distances(self) -> tuple[int, int]:
        '''Использовать вместо max_seek, так как теперь буфер может изменяться'''
        return (
            self._align(0),
            len(self._buf) - self._align(1) - 1
        )

    def insert(self, i: int, *items: RendererEntity):
        i = self._align(i)
        self._buf[i:i] = items
        if i <= self._center:
            self._real_index += len(items)
            self._center += len(items)

    def remove(self, i: int, count: int, rtl = False):
        i = self._align(i)
        if count <= 0:
            return
        if rtl:
            # Режим Backspace: удаляем элементы СЛЕВА от i
            # Диапазон: [i - count, i)
            # max(0, ...) нужен, чтобы не уйти в отрицательные индексы
            start = max(0, i - count)
            end = i
        else:
            # Режим Delete: удаляем элементы СПРАВА от i (включая i)
            # Диапазон: [i, i + count)
            start = i
            end = i + count

        # Используем срез для удаления (работает для list и bytearray)
        del self._buf[start:end]


class InjectionManager:
    def __init__(self,
                 stream: Generator[TokenCursor],
                 tokens: CodeManager,
                 conditions: Iterable[Observation]):
        self._stream = stream
        self._it: Iterator[InjectionPoint] = iter(self)
        self._owner = tokens
        self._conditions = conditions
        self._result: list[RendererEntity] = []
        self._flags: dict[str, int | bool] = {}

    def __iterator__(self):
        for cursor in self._stream:
            matched: list[Observation] = []
            for obs in self._conditions:
                if obs(cursor):
                    matched.append(obs)
            if matched:
                cursor = InjectionPoint(
                    self,
                    cursor.max_seek,
                    len(self._result),
                    matched,
                    cursor._buf
                )
                yield cursor
                self._result.extend(cursor._apply())
            else:
                self._result.extend(cursor._buf)

    def __iter__(self) -> Iterator[InjectionPoint]:
        self._it = self.__iterator__()
        return self._it

    def apply(self, pool: list[Injection]):
        for point in self:
            for injection in pool:
                injection(point)

    def __next__(self) -> InjectionPoint:
        return next(self._it)

    def result(self) -> list[RendererEntity]:
        return self._result


def manage_code(tokens: TokenList, map: SourceMap) -> CodeManager:
    analyzer = ASTNodeAnalyzer(map.get("origin", {})) # type: ignore
    analyzer._process()
    return CodeManager(analyzer, map, tokens)


def observable(
    observation: Callable[[TokenCursor | NodePathElement], bool | None],
    before: list[Observation], name: str = "", only_node: bool = False
) -> Observation:
    @wraps(observation)
    def wrapper(cur: TokenCursor | NodePathElement) -> bool | None:
        for obs in before:
            if obs(cur) is False:
                return False
        if only_node and isinstance(cur, TokenCursor) and isinstance(cur[0], Token):
            cur = cur[0].ast_node  # type: ignore
        return observation(cur)

    wrapper.accepts_node_only = only_node  # type: ignore
    if not name:
        name = observation.__name__
    wrapper.id = name  # type: ignore
    return wrapper  # type: ignore [return-value]


def injection_for(
    injection: Callable[[InjectionPoint], None], *for_: Observation
) -> Injection:

    @wraps(injection)
    def wrapper(point: InjectionPoint) -> bool:
        matched = set(for_) & set(point.matched_conditions)
        if matched:
           injection(point)
           return True
        return False

    wrapper.conditions = for_  # type: ignore
    return wrapper  # type: ignore [return-value]
