import itertools
from dataclasses import dataclass, field
from typing import Optional, Any, Self

from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.abstractions import ActionSpec, TransitionSpec, Effects, Constraints, ConstructSpec
from src.common_utils import DictLikeDataclass

from src.serializers.types import FactSerializable
from src.types import Node


@dataclass
class Metadata(DictLikeDataclass):
    """General metadata for actions, transitions, and nodes"""
    assumed_value: Optional[bool] = None
    # ast_node: Optional[str] = None
    abstract_action: Optional['ActionSpec'] = None
    abstract_transition: Optional['TransitionSpec'] = None
    wrapped_ast: Optional[ASTNodeWrapper] = None
    primary: Optional[bool] = None
    is_after_last: Optional[bool] = None
    call_count: int = 0  # Счётчик вызовов для функций
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


class IDGen:
    def __init__(self, start: int=1):
        self._c = itertools.count(start)
    def next(self, prefix="id"):
        return f"{prefix}_{next(self._c)}"


idgen = IDGen(100)


@dataclass(kw_only=True)
class Node(FactSerializable):
    id: str
    role: str
    kind: Optional[str] = None
    cfg: 'CFG' = None
    effects: list[Effects] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)
    # # If node wraps a subgraph, keep reference
    # subgraph: Optional["CFG"] = None


@dataclass(kw_only=True)
class Edge(FactSerializable):
    id: str
    src: str
    dst: str
    cfg: 'CFG' = None
    constraints: Optional[Constraints] = None
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
    def __init__(self, name="cfg", construct: ConstructSpec=None):
        """ Init a CFG and create BEGIN and END nodes """
        self.id = idgen.next(name)
        self.name: str = name
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

        self._init_boundaries(construct)

    def _init_boundaries(self, construct: ConstructSpec | None):
        # Извлекаем метаданные для BEGIN и END узлов из construct, если он передан
        begin_metadata = None
        end_metadata = None

        if construct:
            # Получаем ActionSpec для BEGIN и END из construct
            begin_action = construct.id2action.get(BEGIN)
            end_action = construct.id2action.get(END)
            if begin_action:
                begin_metadata = Metadata(abstract_action=begin_action)
            if end_action:
                end_metadata = Metadata(abstract_action=end_action)

        # init boundaries с метаданными
        self.begin_node = self.add_node(BEGIN, BEGIN, metadata=begin_metadata)
        self.end_node = self.add_node(END, END, metadata=end_metadata)

    def _add_edge(self, *other_edges: Edge):
        """ Add edges to the CFG, skipping duplicates """
        for e in other_edges:
            if any(e.compare(e2) for e2 in self.edges):
                continue
            self.edges.append(e)

    def add_node(self, kind: str, role: str=None, metadata: Metadata=None, subgraph: Self=None) -> Node | tuple[Node, Node]:
        """ Add a node to the CFG. If subgraph is provided, it will be wrapped in enter and leave nodes.
            Returns the node or a tuple of enter and leave nodes if subgraph is provided. """
        # Извлекаем effects из ActionSpec, если есть
        final_effects = []
        if metadata and metadata.abstract_action:
            if metadata.abstract_action.effects:
                final_effects = metadata.abstract_action.effects

        if not subgraph:
            # Node is an atom (inline).
            nid = idgen.next(kind)
            node = Node(id=nid, kind=kind, role=role,
                        metadata=metadata or Metadata(), 
                        effects=final_effects,
                        cfg=self)
            self.nodes[nid] = node
            return node
        else:
            # Node is a wrapper over a compound.
            kind = 'enter__' + subgraph.name
            nid = idgen.next(kind)
            enter_node = Node(id=nid, kind=kind, role=role, 
                             metadata=metadata or Metadata(),
                             effects=final_effects,
                             cfg=self)
            self.nodes[nid] = enter_node
            
            kind = 'leave__' + subgraph.name
            nid = idgen.next(kind)
            leave_node = Node(id=nid, kind=kind, role=role, 
                             metadata=metadata or Metadata(), 
                             effects=final_effects,
                             cfg=self)
            self.nodes[nid] = leave_node

            # add everything from subgraph (guard for the case of direct recursion when subgraph is the same as self)
            if subgraph is not self:
                self.merge(subgraph)

            # connect subgraph
            self.connect(enter_node, subgraph.begin_node)
            self.connect(subgraph.end_node, leave_node)
            # return both
            return enter_node, leave_node

    def merge(self, subgraph: Self | None):
        """ add everything from subgraph, skipping duplicate edges and nodes """
        self.nodes |= subgraph.nodes
        self._add_edge(*subgraph.edges)

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
            print(" o", nid, n.kind, n.role, info)
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
            print(" o", nid, n.kind, n.role, info)
            print()

        print()
        node_ids = [n.id for n in self.nodes.values()]
        for i, e in enumerate(self.edges):
            print(f"{i+1:2}  ", e.src, "->", e.dst, e.constraints or "", e.metadata or "")
            if e.src not in node_ids:
                print("    FROM NOWHERE! (? ->  )")
            if e.dst not in node_ids:
                print("    TO NOWHERE!   (  -> ?)")

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
