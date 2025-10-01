import itertools
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Self

from adict import adict

from src.types import Node

# CFG classes implemented using constructs.

BEGIN = 'BEGIN'
END = 'END'


class IDGen:
    def __init__(self, start: int=1):
        self._c = itertools.count(start)
    def next(self, prefix="id"):
        return f"{prefix}_{next(self._c)}"


idgen = IDGen(100)


@dataclass
class Node:
    id: str
    role: str
    kind: Optional[str] = None
    metadata: adict = field(default_factory=adict)
    # # If node wraps a subgraph, keep reference
    # subgraph: Optional["CFG"] = None


@dataclass
class Edge:
    src: str
    dst: str
    constraints: Optional[Dict[str, Any]] = None
    metadata: adict = field(default_factory=adict)


class CFG:
    def __init__(self, name="cfg"):
        """ Init a CFG and create BEGIN and END nodes """
        self.name = name
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        # init boundaries
        self.begin_node = self.add_node(BEGIN, BEGIN)
        self.end_node = self.add_node(END, END)

    def add_node(self, kind: str, role: str=None, metadata: dict=None, subgraph: Self=None) -> Node | tuple[Node, Node]:
        """ Add a node to the CFG. If subgraph is provided, it will be wrapped in enter and leave nodes.
            Returns the node or a tuple of enter and leave nodes if subgraph is provided. """
        if not subgraph:
            # Node is an atom.
            nid = idgen.next(kind)
            node = Node(id=nid, kind=kind, role=role, metadata=metadata or adict())
            self.nodes[nid] = node
            return node
        else:
            # Node is a wrapper over a compound.
            kind = 'enter-' + subgraph.name
            nid = idgen.next(kind)
            enter_node = Node(id=nid, kind=kind, role=role,
                              # metadata=metadata or {}  # No effects on enter!?
                              )
            self.nodes[nid] = enter_node
            kind = 'leave-' + subgraph.name
            nid = idgen.next(kind)
            leave_node = Node(id=nid, kind=kind, role=role, metadata=metadata or adict())
            self.nodes[nid] = leave_node
            # add everything from subgraph
            self.nodes |= subgraph.nodes
            self.edges += subgraph.edges
            # connect subgraph
            self.connect(enter_node, subgraph.begin_node)
            self.connect(subgraph.end_node, leave_node)
            # return both
            return enter_node, leave_node

    def connect(self, src: Node | str, dst: Node | str, constraints=None, metadata=None):
        src_id = src.id if isinstance(src, Node) else src
        dst_id = dst.id if isinstance(dst, Node) else dst
        e = Edge(src=src_id, dst=dst_id, constraints=constraints, metadata=metadata or {})
        self.edges.append(e)
        return e

    def debug(self):
        print(f"CFG {self.name}: nodes={len(self.nodes)} edges={len(self.edges)}", )
        for nid,n in self.nodes.items():
            print(" ○", nid, n.kind, n.role, n.metadata or "", )#("(subgraph)" if n.subgraph else ""))
        for e in self.edges:
            print("  ", e.src, "->", e.dst, e.constraints or "", e.metadata or "")
