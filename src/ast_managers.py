import inspect
from collections.abc import Callable, Generator, Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import wraps
from typing import Any, Literal, Protocol, runtime_checkable

from src.coderenderer.colors import colorize_token
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

    def use_for(self, injection: Callable[["InjectionPoint"], None]) -> "Injection": ...


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
    id: int
    type: str
    field_name: str | None
    field_type: Literal["plain", "map", "collection"]
    container_field_id: int | str | None

    def instanceof(self, match_type: str) -> bool:
        # instanceof check
        if self.type == match_type:
            return True
        parents = ASTNodeAnalyzer.get_node_type_parents(self.type)
        return match_type in (parents or [])

    def get(self, analyzer: "ASTNodeAnalyzer") -> Node | None:
        return analyzer.get(self)

    def has_parent(self, id_or_type: int | str | list[str], strict: bool = False) -> bool:
        if isinstance(id_or_type, str) and not strict:
            return self.find_first_parent(
                lambda x: x.instanceof(id_or_type)) is not None
        return self.find_first_parent(id_or_type) is not None

    def find_first_parent(self, query: str | Iterable[str] | int | Callable[["NodePathElement"], bool | None]) -> "NodePathElement | None":
        """
        Ищет первый совпавший по условию `NodePathElement` ТОЛЬКО среди родителей
        """
        curr = self.parent
        if isinstance(query, str):
            query = lambda x, q=query: x.type == q
        elif isinstance(query, int):
            query = lambda x, q=query: x.id == q
        elif isinstance(query, Iterable):
            query = lambda x, q=query: x.type in q
        while curr is not None and not query(curr):
            curr = curr.parent
        return curr

    def find_first(self, query: str | Iterable[str] | int | Callable[["NodePathElement"], bool | None]) -> "NodePathElement | None":
        '''
        Ищет первый совпавший по условию `NodePathElement` среди текущего и его родителей
        '''
        if isinstance(query, str):
            query = lambda x, q=query: x.type == q
        elif isinstance(query, int):
            query = lambda x, q=query: x.id == q
        elif isinstance(query, Iterable):
            query = lambda x, q=query: x.type in q
        result = query(self)
        if not result:
            return self.find_first_parent(query)
        return self

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
            if isinstance(node, dict) and "id" in node and "type" in node:
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
                        id=node_id,
                        type=node["type"],
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


class SkipStreamIterationException(Exception):
    pass


class TokenCursor:
    '''Указатель на токен (индекс равен 0), вокруг него могут быть другие токены (индексы -1, -2... и +1, +2...) в зависимости от lookaround'''

    def __init__(self, owner: "CodeManager", lookaround: int, real_index: int, buf: "list[RendererEntity] | list_view"):
        self._center = lookaround
        self._lookaround = lookaround
        self._buf: list[RendererEntity] | list_view = buf
        self._owner = owner
        self._real_index = real_index

    def _align(self, index: int) -> int:
        return index + self._center

    def __iter__(self):
        return iter(self._buf)

    def __getitem__(self, offset: int | slice) -> RendererEntity | list[RendererEntity]:
        return self._buf[self._align(offset)] if isinstance(offset, int) \
            else self._buf[self._align(offset.start):self._align(offset.stop)]

    def has_next(self) -> bool:
        return self._align(1) < len(self._buf)

    def _translate_index(self, offset: int | slice) -> int | slice:
        '''
        Крайне не рекомендуется использовать в изменяемых буферах
        Получает реальный индекс элемента в буфере (а не в общем списке токенов!!)
        '''
        if isinstance(offset, slice):
            return slice(self._real_index + offset.start,
                         self._real_index + offset.stop,
                         offset.step
                         )
        return self._real_index + offset

    def token(self, index: int) -> Token | None:
        tok = self[index]
        if isinstance(tok, Token):
            return tok
        return None

    def token_index(self, index: int) -> int | None:
        '''
        Индекс токена в глобальном списке токенов.
        Поддерживает изменяемые буферы
        '''
        tok = self.token(index)
        return self._owner.token_indexof(tok) if tok else None

    def ast_node(self, index: int) -> NodePathElement | None:
        tok = self[index]
        if isinstance(tok, Token) and tok.ast_node is not None:
            return tok.ast_node
        return None

    @property
    def manager(self) -> "CodeManager":
        return self._owner

    @property
    def lookaround(self) -> int:
        '''Заданный 'радиус' доступных токенов вокруг текущего'''
        return self._lookaround


class CodeManager:
    def __init__(self, ast: ASTNodeAnalyzer, source_map: SourceMap, tokens: TokenList):
        self._ast = ast
        self._source_map = source_map
        self._tokens: list[Token] = self._remap(tokens) # type: ignore
        self._code: str = self._source_map.get("source_code", "")  # type: ignore
        self._declarations: DeclarationContainer = {
            "functions": [], "classes": [], "globals": []
        }
        self._last_stream: InjectionManager | None = None
        self._process_declarations()

    @property
    def language(self) -> str:
        return self.source_map.get("language", "") # type: ignore

    def _remap(self, tlist: TokenList) -> list[Token]:
        tokens: list[Token] = tlist.get("items", []) # type: ignore
        results = [colorize_token(Token(
                token.get("id"),
                token.get("value", "").replace("\r", ""),
                token.get("token_type", ""),
                i,
                self._locate(i, token),
                []
            )) for i, token in enumerate(tokens) if not isinstance(token, Token)]
        return results

    def _locate(self, index: int, token: TokenJson) -> NodePathElement | None:
        token_byte_pos: tuple[int, int] | None = token.get("byte_pos", None) # type: ignore
        if not token_byte_pos:
            return None
        map_byteranges: dict[int, tuple[int, int]] = self._source_map.get(
            "byte_positions", {})  # type: ignore

        candidates: list[tuple[int, tuple[int, int]]] = []
        for ast_id, byte_range in map_byteranges.items():
            ast_id = int(ast_id)
            ast_path = self.get_path(ast_id)
            start_byte, length = byte_range
            start_token_byte, token_length = token_byte_pos
            if start_byte <= start_token_byte and \
                start_token_byte + token_length <= start_byte + length \
                    and ast_path and ast_path.type != "program_entry_point":
                    candidates.append((ast_id, (start_byte, length)))
        candidates.sort(key=lambda x: (x[1][1], -x[1][0])) # по уровню вложенности
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
    def last_processed(self) -> Sequence[RendererEntity] | None:
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

    def token_indexof(self, token: Token):
        return self._tokens.index(token)

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
            if newlines := token.has_newline():
                line += newlines
        return None

    def line_number_range(self, ast_node: int | NodePathElement) -> tuple[int, int] | None:
        ast_node_id = ast_node.id if isinstance(ast_node, NodePathElement) else ast_node
        token_start, token_end = self.token_index_range(ast_node_id) or (None, None)
        if token_start is None or token_end is None:
            return None
        start_line = self.line_number(token_start)
        end_line = self.line_number(token_end)
        if start_line is None or end_line is None:
            return None
        return start_line, end_line

    def token_index_range(self, ast_node: int | NodePathElement) -> tuple[int, int] | None:
        ast_node_id = ast_node.id if isinstance(ast_node, NodePathElement) else ast_node
        min_i, max_i = self.token_count, 0
        for i, token in enumerate(self):
            if token.ast_node and (
                token.ast_node.id == ast_node_id or \
                    token.ast_node.has_parent(ast_node_id)
            ):
                min_i = min(min_i, i)
                max_i = max(max_i, i)
        if min_i <= max_i:
            return (min_i, max_i + 1)
        return None

    def is_first_node_token(self, token: Token | int, ast_node: int | NodePathElement):
        ast_node_id = ast_node.id if isinstance(ast_node, NodePathElement) else ast_node
        token_index = self.token_indexof(token) if isinstance(token, Token) else token
        trange = self.token_index_range(ast_node_id)
        if trange:
            return token_index == trange[0]

    def is_last_node_token(self, token: Token | int, ast_node: int | NodePathElement):
        ast_node_id = ast_node.id if isinstance(ast_node, NodePathElement) else ast_node
        token_index = self.token_indexof(token) if isinstance(token, Token) else token
        trange = self.token_index_range(ast_node_id)
        if trange:
            return token_index == (trange[-1] - 1)

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
        '''
        Итератор токен, который имеет курсор текущего просматриваемого элемента с индексом 0,
        а также токены слева и справа, если есть, максимальный радиус задает `lookaround`
        '''
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
                if j < 0 or j >= len(self._tokens):
                    continue
                token = self.get_token(j)
                tokens.append(token if token is not None else {})
            yield TokenCursor(self, lookaround, i, tokens)

    def apply_injections(self,
                         injections: 'list[Injection] | type[InjectionPool]',
                         from_: int | None = None,
                         to: int | None = None,
                         step: int = 1,
                         lookaround: int = 3):
        """
        К токенам применяется набор трансформаций - инъекций,
        где каждая инъекция - совокупность предиката(-ов) её применимости и действия
        Действие имеет курсор, аналогичный `stream`.

        Кнопка не может быть в центральном элементе курсора, но может быть в окружающих.
        Логика их появления не определена, поэтому нельзя полагаться на наличие этих кнопок
        в индексах курсора, отличных от нуля (используйте `stream_ensure_token` или `TokenCursor.token`)
        """
        self._last_stream = InjectionManager(self, None,
            from_, to, step, lookaround)
        return self._last_stream.apply(injections)

    def injection_stream(self,
                         conditions: Iterable[Observation],
                         from_: int | None = None,
                         to: int | None = None,
                         step: int = 1,
                         lookaround: int = 3) -> Generator["InjectionPoint"]:
        """
        Создается итератор, который останавливается только при срабатывании предиката наблюдения

        Курсор аналогичен курсору из `stream`, но обновляется в соответствии
        с добавленными/удаленными элементами на каждом шаге,
        т. е. ссылается на изменяемый буфер.

        Кнопка не может быть в центральном элементе курсора, но может быть в окружающих.
        Логика их появления не определена, поэтому нельзя полагаться на наличие этих кнопок
        в индексах курсора, отличных от нуля (используйте `TokenCursor.token`)
        """
        self._last_stream = InjectionManager(
            self, conditions,
            from_, to, step, lookaround
        )
        yield from self._last_stream


class InjectionPoint(TokenCursor):
    def __init__(self, owner: "InjectionManager", lookaround: int,
                 real_index: int,
                 matched_conditions: list[Observation],
                 buf: "list[RendererEntity] | list_view",
                 context_node: NodePathElement | None = None
                 ):
        super().__init__(owner._owner, lookaround, real_index, buf)
        self._injection_owner = owner
        self._context_node = context_node
        self._matched_conditions = matched_conditions

    @property
    def matched_conditions(self) -> list[Observation]:
        return self._matched_conditions

    @property
    def context_node(self) -> NodePathElement | None:
        return self._context_node

    @property
    def applied_injections_before(self):
        return self._injection_owner._applied_count

    def cancel(self):
        '''Отменяет инъекцию'''
        raise SkipStreamIterationException()

    def push_before(self, *items: RendererEntity):
        self.insert(0, *items)

    def push_after(self, *items: RendererEntity):
        self.insert(1, *items)

    def __setitem__(self, index: int, item: RendererEntity):
        self._buf[self._align(index)] = item
        self._injection_owner._trigger()

    def remove_after(self, count: int): # в пределах lookaround
        self.remove(1, count)

    def remove_before(self, count: int):  # в пределах lookaround
        self.remove(0, count, rtl=True)

    def flag(self, name: str, value: int | bool | None = None) -> int | bool | None:
        self._owner._flags.setdefault(name, value)
        return self._owner._flags[name]

    @property
    def distances(self) -> tuple[int, int]:
        '''Использовать вместо `lookaround`, так как теперь буфер может изменяться'''
        return (
            self._align(0),
            len(self._buf) - self._align(1) - 1
        )

    def insert(self, i: int, *items: RendererEntity):
        aligned_i = self._align(i)
        if i <= 0:
            self._real_index += len(items)
            self._center += len(items)
        self._buf[aligned_i:aligned_i] = items
        self._injection_owner._trigger()

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
        self._injection_owner._trigger()


class list_view:
    def __init__(self, src: list, indices: Iterable[int] | range):
        self._src = src
        self._indices = list(indices)

    def __iter__(self):
        for i in self._indices:
            yield self._src[i]

    def __getitem__(self, i: int | slice):
        if isinstance(i, slice):
            return self._src[self.translate_index(i.start) : self.translate_index(i.stop) : i.step]
        return self._src[self.translate_index(i)]

    def __setitem__(self, i: int | slice, item: Any):
        if isinstance(i, slice):
            start, stop, step = i.indices(len(self._indices))

            if step != 1:
                # Extended slice - размер должен совпадать
                target_indices = self._indices[i]
                if hasattr(item, '__iter__') and not isinstance(item, str):
                    items = list(item)
                    if len(items) != len(target_indices):
                        raise ValueError(
                            f"attempt to assign sequence of size {len(items)} "
                            f"to extended slice of size {len(target_indices)}"
                        )
                    for idx, val in zip(target_indices, items):
                        self._src[idx] = val
                else:
                    for idx in target_indices:
                        self._src[idx] = item
            else:
                # Simple slice - можно вставлять/удалять
                old_indices = self._indices[start:stop]
                items = list(item) if hasattr(item, '__iter__') and not isinstance(item, str) else [item]

                # Определяем позицию вставки в исходном списке
                if start >= len(self._indices):
                    insert_pos = len(self._src)
                elif start == 0 and not self._indices:
                    insert_pos = 0
                else:
                    insert_pos = self._indices[start] if start < len(self._indices) else len(self._src)

                # Удаляем старые элементы (с конца)
                for src_idx in sorted(old_indices, reverse=True):
                    del self._src[src_idx]
                    if src_idx < insert_pos:
                        insert_pos -= 1

                # Вставляем новые элементы
                for offset, val in enumerate(items):
                    self._src.insert(insert_pos + offset, val)

                # Пересчитываем индексы
                deleted_set = set(old_indices)
                new_indices = []

                for idx_pos, idx in enumerate(self._indices):
                    if idx_pos < start or idx_pos >= stop:
                        # Считаем сдвиг
                        deleted_before = sum(1 for d in old_indices if d < idx)
                        added_offset = len(items) if idx >= insert_pos else 0
                        new_indices.append(idx - deleted_before + added_offset)

                # Добавляем новые индексы на место старых
                new_item_indices = list(range(insert_pos, insert_pos + len(items)))
                self._indices = new_indices[:start] + new_item_indices + new_indices[start:]
        else:
            self._src[self._indices[i]] = item

    def __delitem__(self, item: int | slice):
        if isinstance(item, int):
            return self.pop(item)

        # Получаем индексы для удаления
        indices_to_remove = self._indices[item]

        # Проверяем валидность всех индексов
        for idx in indices_to_remove:
            if idx < 0 or idx >= len(self._src):
                raise IndexError(f"source index {idx} out of range")

        # Удаляем из исходного списка (с конца, чтобы не сбить индексы)
        sorted_to_remove = sorted(indices_to_remove, reverse=True)
        for src_idx in sorted_to_remove:
            del self._src[src_idx]

        # Обновляем индексы view
        deleted_set = set(indices_to_remove)
        new_indices = []

        for idx in self._indices:
            if idx in deleted_set:
                continue
            # Считаем смещение
            offset = sum(1 for d in sorted_to_remove if d < idx)
            new_indices.append(idx - offset)

        self._indices = new_indices

    def __len__(self):
        return len(self._indices)

    @property
    def source(self):
        return self._src

    def translate_index(self, i: int | slice) -> int | slice:
        if isinstance(i, slice):
            return slice(self.translate_index(i.start), self.translate_index(i.stop), i.step)
        if i < 0 or i >= len(self._indices):
            raise IndexError(f"Invalid list_view position, {i}")
        return self._indices[i]

    def insert(self, pos: int, item: Any):
        """Вставляет элемент в исходный список и обновляет индексы"""
        # Находим позицию в исходном списке
        if pos < 0 or pos > len(self._indices):
            raise IndexError(f"Position {pos} not found in list_view")
        insert_idx = self._indices[-1] + 1 \
            if pos == len(self._indices) else self._indices[pos]

        # Вставляем в исходный список
        self._src.insert(insert_idx, item)

        # Обновляем все индексы >= insert_idx
        self._indices = [idx + 1 if idx >= insert_idx else idx for idx in self._indices]

        # Добавляем новый индекс
        self._indices.insert(pos, insert_idx)

    def remove(self, item: Any):
        """Удаляет первое вхождение элемента"""
        for i, idx in enumerate(self._indices):
            if self._src[idx] == item:
                self.pop(i)
                return
        raise ValueError(f"{item} not in list_view")

    def pop(self, pos: int = -1):
        """Удаляет элемент по позиции в view"""
        if not self._indices:
            raise IndexError("pop from empty list_view")

        # Получаем индекс в исходном списке
        src_idx = self._indices[pos]
        item = self._src[src_idx]

        # Удаляем из исходного списка
        del self._src[src_idx]

        # Обновляем индексы
        self._indices.pop(pos)
        self._indices = [idx - 1 if idx > src_idx else idx for idx in self._indices]

        return item


class InjectionManager:
    def __init__(self,
                 tokens: CodeManager,
                 conditions: Iterable[Observation] | None = None,
                 from_: int | None = None,
                 to_: int | None = None,
                 step: int | None = None,
                 lookaround: int = 1):
        self._lookaround = lookaround
        self._owner = tokens
        self._conditions = conditions
        self._applied_count = 0
        self._skipped_count = 0
        self._triggered = False
        self._origin = tokens._tokens[from_:to_:step]
        self._result: list[RendererEntity] = list(self._origin) # type: ignore
        self._ptr = -1
        self._flags: dict[str, int | bool] = {}

    def _trigger(self):
        self._triggered = True

    def __detect_trigger(self):
        if self._triggered:
            self._applied_count += 1
            self._triggered = False

    def _count_injected_before(self, abs_pos: int) -> int:
        return sum(
            1 for i, x in enumerate(self._result) if i < abs_pos and not isinstance(x, Token)
        )

    def __next__(self):
        self.__detect_trigger()
        self._ptr += 1
        if self._ptr >= len(self._origin):
            raise StopIteration
        ptr = self._result.index(self._origin[self._ptr])
        begin_index = max(ptr - self._lookaround, 0)
        end_index = min(ptr + self._lookaround + 1, len(self._result))

        buffer = list_view(self._result, range(begin_index, end_index))
        cursor = TokenCursor(self._owner,
                             self._lookaround,
                             begin_index + self._lookaround,
                             buffer)
        matched: list[Observation] = []
        for obs in (self._conditions or []):
            try:
                if obs(cursor):
                    matched.append(obs)
            except SkipStreamIterationException:
                pass
        context_node: NodePathElement | None = None
        if hasattr(cursor, "context_node") and isinstance(getattr(cursor, "context_node"), NodePathElement):  # noqa: B009
            context_node = getattr(cursor, "context_node")  # noqa: B009
        cursor = InjectionPoint(
            self, cursor.lookaround,
            begin_index, matched,
            buffer, context_node
        )
        return cursor

    def __iter__(self) -> Iterator[InjectionPoint]:
        return self

    def apply(self, pool: "list[Injection] | type[InjectionPool]"):
        if isinstance(pool, type) and issubclass(pool, InjectionPool):
            pool = pool.declared_injections()
        self._conditions = observations_from(pool)
        for point in self:
            for injection in pool:
                try:
                    injection(point)
                    self.__detect_trigger()
                except SkipStreamIterationException:
                    self._skipped_count += 1

    def result(self) -> Sequence[RendererEntity]:
        return self._result


def manage_code(tokens: TokenList, source_map: SourceMap) -> CodeManager:
    analyzer = ASTNodeAnalyzer(source_map.get("origin", {})) # type: ignore
    analyzer._process()
    return CodeManager(analyzer, source_map, tokens)


def observable_token(
    before: list[Observation] | None = None,
    name: str = "",
) -> Callable[[Callable], Any]:
    """
    Фабрика декораторов.
    Использование: @observable_token(before=[...], name="...")
    """

    def decorator(observation: Callable[[TokenCursor], bool | None]) -> Any:
        nonlocal name
        if not name:
            name = observation.__name__

        @wraps(observation)
        def wrapper(cur: TokenCursor | NodePathElement) -> bool | None:
            for obs in (before or []):
                # Если условие before не выполнено, прерываем
                if obs(cur) is False:
                    return False
            return observation(cur)  # type: ignore

        # Метаданные
        wrapper.accepts_node_only = False  # type: ignore
        wrapper.id = name  # type: ignore

        # Хелпер для инъекции. Мы передаем сам 'wrapper' как условие,
        # но так как мы вернем staticmethod, используем саму функцию wrapper для регистрации.
        wrapper.use_for = lambda x: injection_for_all(wrapper)(x)  # type: ignore

        # Возвращаем staticmethod, чтобы метод в классе не требовал self
        return staticmethod(wrapper)

    return decorator


def observable_node(before: list[Observation] | None = None, name: str = "") -> Callable[[Callable], Any]:
    """
    Фабрика декораторов.
    Использование: @observable_node(name="is_atomic")
    """

    def decorator(observation: Callable[[NodePathElement], bool | None]) -> Any:
        nonlocal name
        if not name:
            name = observation.__name__

        @wraps(observation)
        def wrapper(cur: TokenCursor | NodePathElement) -> bool | None:
            for obs in (before or []):
                res = obs(cur)
                if not res:
                    return res

            # Логика приведения типов
            if isinstance(cur, TokenCursor):
                tok = cur[0]
                if isinstance(tok, Token) and tok.ast_node:
                    cur = tok.ast_node
                else:
                    raise ValueError("Required Token as RendererEntity for observation")

            return observation(cur)

        # Метаданные
        wrapper.accepts_node_only = True  # type: ignore
        wrapper.id = name  # type: ignore
        wrapper.use_for = lambda x: injection_for_all(wrapper)(x)  # type: ignore

        # Возвращаем staticmethod
        return staticmethod(wrapper)

    return decorator


def injection_for_any(*for_: Observation) -> Callable[[Callable], Any]:
    """
    Декоратор-фабрика.
    Использование: @injection_for(condition1, condition2)
    """

    def decorator(injection: Callable[[InjectionPoint], None]):
        @wraps(injection)
        def wrapper(point: InjectionPoint) -> bool:
            matched = set(for_) & set(point.matched_conditions)
            if matched:
                injection(point)
                return True
            return False

        wrapper.conditions = for_  # type: ignore
        return wrapper

    return decorator


def injection_for_all(*for_: Observation) -> Callable[[Callable], Any]:
    """
    Декоратор-фабрика.
    Использование: @injection_for(condition1, condition2)
    """

    def decorator(injection: Callable[[InjectionPoint], None]):
        @wraps(injection)
        def wrapper(point: InjectionPoint) -> bool:
            base = set(for_)
            matched = set(for_) & set(point.matched_conditions)
            if len(matched) == len(base):
                injection(point)
                return True
            return False

        wrapper.conditions = [join_observations(for_)]  # type: ignore
        return wrapper

    return decorator


class InjectionPool:
    def __init_subclass__(cls):
        for name, attr in cls.__dict__.items():
            if callable(attr) and not name.startswith("__"):
                setattr(cls, name, staticmethod(attr))

    def __new__(cls, *args, **kwargs):
        raise TypeError("Injection pool classes cannot be instantiated")

    @classmethod
    def declared_observations(cls) -> list[Observation]:
        """Возвращает все методы класса, соответствующие протоколу Observation"""
        observations = []
        # inspect.getmembers автоматически разворачивает дескрипторы (staticmethod),
        # возвращая сами функции-обертки, у которых есть нужные атрибуты.
        for name, value in inspect.getmembers(cls):
            if not name.startswith("__") and isinstance(value, Observation):
                observations.append(value)
        return observations

    @classmethod
    def declared_injections(cls) -> list[Injection]:
        """Возвращает все методы класса, соответствующие протоколу Injection"""
        injections = []
        for name, value in inspect.getmembers(cls):
            if not name.startswith("__") and isinstance(value, Injection):
                injections.append(value)
        return injections


def join_observations(obs: Sequence[Observation], name: str = "") -> Observation:
    if len(obs) == 1:
        return obs[0]

    def joined_obs(cur: TokenCursor) -> bool | None:
        res = False
        for o in obs:
            res = o(cur)
            if not res:
                return res
        return res

    return observable_token(name=name)(joined_obs)


def observations_from(pool: list[Injection]) -> list[Observation]:
    res = []
    for inj in pool:
        res.extend(inj.conditions)
    return res


def stream_require[T](obj: T | None,
                      msg: str | None = None) -> T:
    '''
    Пропускает итерацию (наблюдение или инъекция), если значение - None
    Пропускает только при вызове `apply_injections`, в остальных случаях - исключение
    '''
    if obj is None:
        raise SkipStreamIterationException(msg or "Stream point requires non null element")
    return obj


def stream_ensure_token(obj: Any) -> Token:
    """
    Пропускает итерацию (наблюдение или инъекция), если значение не типа `Token`
    Пропускает только при вызове `apply_injections`, в остальных случаях - исключение
    """
    if not isinstance(obj, Token):
        raise SkipStreamIterationException("Stream point requires token at specified position")
    return obj


def is_language(name: str) -> Observation:

    @observable_token()
    def is_language_instance(cur: TokenCursor) -> bool | None:
        return cur.manager.language == name

    return is_language_instance

def is_language_not_in(names: list[str]) -> Observation:
    @observable_token()
    def is_notlanguage_instance(cur: TokenCursor) -> bool | None:
        return cur.manager.language not in names

    return is_notlanguage_instance
