import itertools
import sys
from dataclasses import dataclass, field
from typing import Iterable, Optional, Self, TYPE_CHECKING

from src.cfg.abstractions import (
    DEFAULT_APPEARANCE_PROFILE,
    ActionSpec,
    AppearanceType,
    Constraints,
    ConstructSpec,
    Effects,
    TransitionSpec, ActionKind, OptionalBoolValue,
)
from src.cfg.ast_wrapper import ASTNodeWrapper
from src.common_utils import DictLikeDataclass, SelfValidatedEnum
from src.serializers.types import FactSerializable

if TYPE_CHECKING:
    from src.cfg.reachability import PathInfo


@dataclass
class TraceAct(DictLikeDataclass):
    """Акт выполнения программы в трассе.
    
    Представляет одно действие в последовательности выполнения программы.
    Содержит ссылки на AST-узел, CFG-узел, спецификацию действия и связи с другими актами.
    
    Attributes:
        wrapped_ast: Обёртка AST-узла, соответствующего этому акту
        cfg_node: Узел CFG, соответствующий этому акту
        action_spec: Спецификация действия (если есть)
        corresponding_end: Связанный акт конца блока (для BEGIN/END пар)
        is_known_correct: Флаг корректности акта
        condition_value: Значение условия для узлов-условий (OptionalBoolValue/None)
        directly_before_of: Следующий акт в трассе, формирующий цепочку выполнения.
                           Устанавливается при построении трассы, связывая акты в порядке
                           их выполнения. Последний акт имеет None.
        button_type: Тип кнопки для UI (не экспортируется в LOQI)
    """
    wrapped_ast: ASTNodeWrapper
    cfg_node: 'Node'
    action_spec: ActionSpec | None
    corresponding_end: 'TraceAct | None'
    is_known_correct: bool
    condition_value: OptionalBoolValue | None = None
    directly_before_of: 'TraceAct | None' = None  # Следующий акт в трассе (цепочка выполнения)
    button_type: str | None = None # Нужно для корректного поиска действий трассы. Экспортировать не нужно!


@dataclass
class Metadata(DictLikeDataclass):
    """General metadata for transitions and nodes"""
    assumed_value: bool | None = None
    # ast_node: Optional[str] = None
    abstract_action: Optional['ActionSpec'] = None
    abstract_transition: Optional['TransitionSpec'] = None
    wrapped_ast: ASTNodeWrapper | None = None
    primary: bool | None = None  # TODO: remove
    is_after_last: bool | None = None
    call_count: int = 0  # Счётчик вызовов для функций
    has_corresponding_end: Optional['Node'] = None
    # # Additional fields can be added as needed
    # custom: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Проверяет, содержит ли metadata значимую информацию."""
        return (
            self.assumed_value is None and
            self.abstract_action is None and
            self.abstract_transition is None and
            self.wrapped_ast is None and
            self.primary is None and
            self.is_after_last is None and
            self.call_count == 0
        )


# CFG classes implemented using constructs.

BEGIN = 'BEGIN'
END = 'END'


class NodeKind(SelfValidatedEnum):
    """Типы узлов CFG."""
    BEGIN = BEGIN
    END = END
    ATOM = "atom"
    ANY = "any"

# class NodeRole(SelfValidatedEnum):
#     """Роли узлов CFG."""
#     CONDITION = 'condition'
#     FUNC_CALL = 'func_call'
#     CONSTRUCT = "construct"  # ???
#     # BLOCK = "block"  # ??? TODO
#     ANY = "any"


class IDGen:
    def __init__(self, start: int=1):
        self._c = itertools.count(start)
        self._start = start

    def reset(self):
        self._c = itertools.count(self._start)

    def next(self, prefix="id"):
        return f"{prefix}_{next(self._c)}"


idgen = IDGen(100)


@dataclass(kw_only=True)
class Node(FactSerializable):
    id: str
    role_in_construct: str  # for internal usage
    kind: NodeKind
    appearance: AppearanceType = AppearanceType.NONE
    cfg: 'CFG | None' = None
    effects: list[Effects] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)
    direct_out_paths: list['PathInfo'] = field(default_factory=list, repr=False)
    direct_in_paths: list['PathInfo'] = field(default_factory=list, repr=False)
    # # If node wraps a subgraph, keep reference
    # subgraph: Optional["CFG"] = None

    def describe(self) -> str:
        ast_id = self.metadata.wrapped_ast.ast_node.get('id') if self.metadata.wrapped_ast else None
        return f'Node( id={self.id}, kind={self.kind.value}, role_in_construct={self.role_in_construct}, action={self.metadata.abstract_action.role if self.metadata.abstract_action else None}, ast_id={ast_id!r} )'

    def is_mandatory(self) -> bool:
        return self.appearance == AppearanceType.MANDATORY

    def is_condition(self) -> bool:
        """ Проверяет, является ли узел условием. 
        Обратите внимание, что условие может быть прозрачным (т.е. не обязательным): это может наблюдаться в цикле `for(;;) { ... }` или `while(true) { ... }` """
        return self.metadata.abstract_action and self.metadata.abstract_action.kind.has('condition')

    def clear_direct_paths(self) -> None:
        """Удалить информацию о прямых путях, связанных с узлом."""
        self.direct_out_paths.clear()
        self.direct_in_paths.clear()

    def set_direct_paths(
        self,
        *,
        outgoing: Iterable['PathInfo'] | None = None,
        incoming: Iterable['PathInfo'] | None = None,
    ) -> None:
        """Перезаписать списки прямых путей (исходящих/входящих)."""
        if outgoing is not None:
            self.direct_out_paths = list(outgoing)
        if incoming is not None:
            self.direct_in_paths = list(incoming)

    def register_direct_path(self, path: 'PathInfo', *, incoming: bool = False) -> None:
        """Добавить прямой путь к исходящим или входящим путям."""
        target = self.direct_in_paths if incoming else self.direct_out_paths
        if path not in target:
            target.append(path)

@dataclass(kw_only=True)
class Edge(FactSerializable):
    id: str
    src: str
    dst: str
    cfg: 'CFG | None' = None
    constraints: Constraints | None = None
    effects: list[Effects] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)

    def compare(self, other: Self):
        """ Compare edges for equality of src, dst, constraints, metadata to make sure we won't add duplicates """
        return (# self.id == other.id and
                self.src == other.src and
                self.dst == other.dst and
                self.constraints == other.constraints #and
                # self.effects == other.effects and
                # self.metadata.ast_node is other.metadata.ast_node
        )


class CFG:
    def __init__(self, name="cfg", construct: ConstructSpec=None, *, with_boundaries: bool = True):
        """Init a CFG. By default, creates BEGIN and END boundary nodes."""
        self.id = idgen.next(name)
        self.name: str = name
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.begin_node: Node | None = None
        self.end_node: Node | None = None

        if with_boundaries:
            self._init_boundaries(construct)

    @classmethod
    def create_empty(cls, name="cfg", construct: ConstructSpec | None = None) -> Self:
        """Create a minimal CFG with BEGIN and END connected directly."""
        cfg = cls(name, construct=construct)
        cfg.connect(cfg.begin_node, cfg.end_node)
        return cfg

    @classmethod
    def create_atomic(
        cls,
        name: str,
        *,
        role: str | None = None,
        metadata: Metadata | None = None,
    ) -> Self:
        """Create a CFG consisting of a single node that acts as both BEGIN and END."""
        # Node is expected to be an atom (inline).
        kind = NodeKind.ATOM
        cfg = cls(name, with_boundaries=False)

        metadata = metadata or Metadata()
        effects: list[Effects] = []
        if metadata.abstract_action and metadata.abstract_action.effects:
            effects = metadata.abstract_action.effects

        kind = NodeKind(kind)
        node_id = idgen.next(kind.value)
        node = Node(
            id=node_id,
            kind=kind,
            role_in_construct=role,
            metadata=metadata,
            effects=effects,
            cfg=cfg,
        )

        cfg.nodes[node_id] = node
        cfg.begin_node = node
        cfg.end_node = node

        return cfg

    def _init_boundaries(self, construct: ConstructSpec | None):
        # Извлекаем метаданные для BEGIN и END узлов из construct, если он передан
        begin_metadata = None
        end_metadata = None

        if construct:
            # Получаем ActionSpec для BEGIN и END из construct
            begin_action = construct.role2action.get(BEGIN)
            end_action = construct.role2action.get(END)
            if begin_action:
                begin_metadata = Metadata(abstract_action=begin_action)
            if end_action:
                end_metadata = Metadata(abstract_action=end_action)

        # init boundaries с метаданными
        self.begin_node = self.add_node(NodeKind.BEGIN, BEGIN, metadata=begin_metadata)
        self.end_node = self.add_node(NodeKind.END, END, metadata=end_metadata)

        # set has_corresponding_end
        self.begin_node.metadata.has_corresponding_end = self.end_node

    def _add_edge(self, *other_edges: Edge):
        """ Add edges to the CFG, merging edges with same src and dst by combining constraints and effects """
        for e in other_edges:
            # Проверяем, есть ли уже Edge с такими же src и dst
            existing_edge = None
            for existing in self.edges:
                if existing.src == e.src and existing.dst == e.dst:
                    existing_edge = existing
                    break
            
            if existing_edge:
                # Найден Edge с такими же src и dst - объединяем constraints и effects
                # Объединяем constraints
                merged_constraints = Constraints.merge(
                    existing_edge.constraints,
                    e.constraints
                )
                
                # Объединяем effects (списки effects)
                existing_effects_list = existing_edge.effects or []
                new_effects_list = e.effects or []
                
                # Пытаемся объединить каждый effect из нового списка с существующими
                merged_effects_list = list(existing_effects_list)
                
                for new_effect in new_effects_list:
                    merged_with_existing = False
                    for i, existing_effect in enumerate(merged_effects_list):
                        merged_effect = Effects.merge(existing_effect, new_effect)
                        if merged_effect is not None:
                            # Успешно объединено
                            merged_effects_list[i] = merged_effect
                            merged_with_existing = True
                            break
                    
                    if not merged_with_existing:
                        # Не удалось объединить - добавляем как новый
                        merged_effects_list.append(new_effect)
                
                # Обновляем существующий Edge
                existing_edge.constraints = merged_constraints
                existing_edge.effects = merged_effects_list if merged_effects_list else None
                
                # Объединяем metadata: если у обоих есть abstract_transition, сохраняем существующий
                # (в будущем можно расширить для хранения списка transitions)
                
                # Edge объединен с существующим
            else:
                # Полное совпадение (дубликат) - пропускаем
                if any(e.compare(e2) for e2 in self.edges):
                    continue
                
                # Новый Edge - добавляем
                self.edges.append(e)
                # update .cfg for newly added edge
                e.cfg = self

    def add_existing_node(self,
                 *nodes: Node):
        """ Bring some existing node from other CFG to this CFG as-is. """
        for node in nodes:
            self.nodes[node.id] = node
        # return node


    def add_node(self,
                 kind: str | NodeKind,
                 role: str=None,
                 metadata: Metadata=None,
                 subgraph: Self=None) -> Node | tuple[Node, Node]:
        """ Add a node to the CFG. If subgraph is provided, it will be wrapped in enter and leave nodes.
            Returns the node or a tuple of enter and leave nodes if subgraph is provided. """

        final_metadata = metadata or Metadata()
        # Извлекаем effects из ActionSpec, если есть
        # Effects применяются только к ATOM и END, не к BEGIN
        final_effects = []
        if final_metadata.abstract_action:
            if final_metadata.abstract_action.effects:
                node_kind = NodeKind(kind)
                # Effects применяются только к ATOM и END, не к BEGIN
                if node_kind != NodeKind.BEGIN:
                    final_effects = final_metadata.abstract_action.effects

        if not subgraph:
            # Узел может быть служебным началом или концом CFG, или атомом (в середине).

            node_kind = NodeKind(kind)
            nid = idgen.next(node_kind.value)
            node = Node(id=nid, kind=node_kind, role_in_construct=role,
                        metadata=final_metadata,
                        effects=final_effects,
                        cfg=self)
            self.nodes[nid] = node
            
            return node
        else:
            # Node is a wrapper over a compound.
            # Add everything from subgraph:
            if subgraph is not self:
                # (guard for the case of direct recursion when subgraph is the same as self)
                self.merge(subgraph)

            if not metadata:
                # simply embedded subgraph; return references to its bounds.
                return subgraph.begin_node, subgraph.end_node

            # Metadata is not empty,
            # Make intermediate connections to the subgraph...

            kind = NodeKind.BEGIN
            nid = idgen.next(kind.value)
            enter_node = Node(id=nid, kind=kind, role_in_construct=role,
                              metadata=final_metadata,
                              effects=[],  # no effects for begin node.
                              cfg=self)
            self.nodes[nid] = enter_node

            # Для leave_node (END) нужно пересчитать effects, так как он должен получать effects из ActionSpec
            leave_effects = []
            if final_metadata.abstract_action and final_metadata.abstract_action.effects:
                # END узлы должны получать effects
                leave_effects = final_metadata.abstract_action.effects

            kind = NodeKind.END
            nid = idgen.next(kind.value)
            leave_node = Node(id=nid, kind=kind, role_in_construct=role,
                              metadata=final_metadata,
                              effects=leave_effects,
                              cfg=self)
            self.nodes[nid] = leave_node

            # connect subgraph
            self.connect(enter_node, subgraph.begin_node)
            self.connect(subgraph.end_node, leave_node)
            # return both
            return enter_node, leave_node

    def merge(self, subgraph: Self | None):
        """ add everything from subgraph, skipping duplicate edges and nodes """
        self.nodes |= subgraph.nodes
        self._add_edge(*subgraph.edges)

        # update .cfg for newly added nodes
        for node in subgraph.nodes.values():
            node.cfg = self
            node.role_in_construct = node.role_in_construct and ('.' + node.role_in_construct)  # change to prevent conflicts... ?

    def connect(self, src: Node | str, dst: Node | str, constraints=None, metadata: Metadata=None):
        src_id = src.id if isinstance(src, Node) else src
        dst_id = dst.id if isinstance(dst, Node) else dst

        # Автоматически извлекаем constraints и effects из TransitionSpec
        final_constraints = constraints
        final_effects = []

        if metadata and metadata.abstract_transition:
            # Если constraints не переданы явно, берём из transition
            if final_constraints is None and metadata.abstract_transition.constraints:
                final_constraints = metadata.abstract_transition.constraints

            # Извлекаем effects из transition
            if metadata.abstract_transition.effects:
                final_effects = metadata.abstract_transition.effects

        e = Edge(id=idgen.next(), src=src_id, dst=dst_id,
                 constraints=final_constraints,
                 effects=final_effects,
                 metadata=metadata or Metadata(),
                 cfg=self)
        self._add_edge(e)
        return e

    def debug(self):
        print(f"CFG {self.name}: nodes={len(self.nodes)} edges={len(self.edges)}", )
        for nid, n in self.nodes.items():
            info = {}
            if n.metadata.abstract_action:
                info['abstract_action'] = n.metadata.abstract_action.role
            if n.metadata.wrapped_ast:
                info['ast'] = n.metadata.wrapped_ast.describe()
            print(" o", nid, n.kind.value, n.role_in_construct, info)
            # print all outgoing edges
            for e in self.edges:
                if e.src == nid:
                    print("   ->", e.dst, " __",
                          e.constraints or "",
                          e.metadata,
                          # ((m := e.metadata) and m.abstract_transition and m.abstract_transition.to) or "",
                          # ((m := e.metadata) and m.abstract_transition and m.abstract_transition.constraints) or "",
                          # ((m := e.metadata) and m.primary is not None and ('primary' if m.primary else 'default-exit.')) or "",
                    )
        print()
        print()
        print()
        print('<<<<<')
        print()
        for nid, n in self.nodes.items():
            # print all incoming edges
            for e in self.edges:
                if e.dst == nid:
                    print("   ->>", e.src, " __",
                          e.constraints or "",
                          ((m := e.metadata) and m.abstract_transition and m.abstract_transition.from_ + ' >>') or "",
                          ((m := e.metadata) and m.abstract_transition and m.abstract_transition.constraints) or "",
                    )
            info = {}
            if n.metadata.abstract_action:
                info['abstract_action'] = n.metadata.abstract_action.role
            if n.metadata.wrapped_ast:
                info['ast'] = n.metadata.wrapped_ast.describe()
            print(" o", nid, n.kind.value, n.role_in_construct, info)
            print()

        print()
        node_ids = [n.id for n in self.nodes.values()]
        for i, e in enumerate(self.edges):
            print(f"{i+1:2}  ", e.src, "->", e.dst, e.constraints or "", e.metadata or "")
            if e.src not in node_ids:
                print("    FROM NOWHERE! (? ->  )")
            if e.dst not in node_ids:
                print("    TO NOWHERE!   (  -> ?)")

    def debug_paths(self):

        print('<<<<<')
        print()
        for nid, n in self.nodes.items():
            # print all incoming edges
            for p in n.direct_in_paths or ():
                # if p.dst == nid:
                    print("   ->>", p.from_.id, " __",
                          p.constraints or "",
                          ' >>path-to>>',
                          p.to_.id,
                    )

            # print all outgoing edges
            for p in n.direct_out_paths or ():
                # if p.dst == nid:
                    print("   ->>", p.from_.id, " __",
                          p.constraints or "",
                          ' >>path-to>>',
                          p.to_.id,
                    )
            # info = {}
            # if n.metadata.abstract_action:
            #     info['abstract_action'] = n.metadata.abstract_action.role
            # if n.metadata.wrapped_ast:
            #     info['ast'] = n.metadata.wrapped_ast.describe()
            # print(" o", nid, n.kind.value, n.role_in_construct, info)
            # print()
        print('>>>>>>')


    def edges_from_node(self, node: Node) -> list[Edge]:
        return [e for e in self.edges if e.src == node.id]

    def _is_node_insignificant(self, node: Node) -> bool:
        """Проверяет, является ли узел незначимым (можно удалить)."""
        # (!) BEGIN и END могут быть незначимы, когда промежуточны.
        # if node.role in (BEGIN, END):
        #     return False

        # Проверяем наличие эффектов
        if node.effects:
            return False

        # Проверяем метаданные
        if not node.metadata.is_empty():
            return False

        # Проверяем, что узел не является развилкой
        incoming = [e for e in self.edges if e.dst == node.id]
        outgoing = [e for e in self.edges if e.src == node.id]

        # Узел незначимый, если ровно 1 вход и 1 выход
        return len(incoming) == 1 and len(outgoing) == 1

    def _is_edge_insignificant(self, edge: Edge) -> bool:
        """Проверяет, является ли ребро незначимым (можно удалить)."""
        # Проверяем constraints
        if edge.constraints is not None:
            return False

        # Проверяем effects
        if edge.effects:
            return False

        # Проверяем метаданные
        return edge.metadata.is_empty()

    def optimize(self) -> int:
        """
        Оптимизирует CFG, удаляя незначимые транзитные узлы.
        Возвращает количество удалённых узлов.
        """
        removed_count = 0

        # Повторяем, пока есть что удалять
        while True:
            # Находим один узел для удаления за итерацию
            node_to_remove = None

            for node_id, node in self.nodes.items():
                if self._is_node_insignificant(node):
                    # Находим входящее и исходящее рёбра
                    incoming = [e for e in self.edges if e.dst == node_id]
                    outgoing = [e for e in self.edges if e.src == node_id]

                    # Должно быть ровно 1 входящее и 1 исходящее (проверено в _is_node_insignificant)
                    edge_in = incoming[0]
                    edge_out = outgoing[0]

                    # Проверяем, что хотя бы одно из рёбер незначимое
                    if self._is_edge_insignificant(edge_in) or self._is_edge_insignificant(edge_out):
                        node_to_remove = (node_id, edge_in, edge_out)
                        break  # Обрабатываем только один узел за итерацию

            # Если нечего удалять, выходим
            if not node_to_remove:
                break

            # Удаляем узел и перенаправляем рёбра
            node_id, edge_in, edge_out = node_to_remove

            # Создаём новое ребро напрямую от src edge_in к dst edge_out
            # Если одно из рёбер значимое, сохраняем его метаданные
            if self._is_edge_insignificant(edge_in):
                # Входящее ребро незначимое, используем данные из исходящего
                new_constraints = edge_out.constraints
                new_effects = edge_out.effects
                new_metadata = edge_out.metadata
            else:
                # Исходящее ребро незначимое, используем данные из входящего
                new_constraints = edge_in.constraints
                new_effects = edge_in.effects
                new_metadata = edge_in.metadata

            new_edge = Edge(
                id=idgen.next('optimized_edge'),
                src=edge_in.src,
                dst=edge_out.dst,
                cfg=self,
                constraints=new_constraints,
                effects=new_effects,
                metadata=new_metadata
            )

            # Удаляем старые рёбра
            self.edges.remove(edge_in)
            self.edges.remove(edge_out)

            # Добавляем новое ребро
            self._add_edge(new_edge)

            # Удаляем узел
            del self.nodes[node_id]

            removed_count += 1

        return removed_count
