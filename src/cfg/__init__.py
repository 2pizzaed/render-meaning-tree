# Read constructs.yml from /mnt/data and build dataclasses for constructs.
# Then implement a CFG builder that loads constructs, creates dataclasses, and uses them to create handlers.
# The demo will show reading the YAML, instantiating constructs, and creating a simple CFG where
# subgraphes are inlined seamlessly when used as atomic actions in a sequence.

from dataclasses import dataclass, field
from operator import index
from typing import Dict, List, Optional, Any, Callable, Tuple, Self
import yaml, os, itertools, copy


from adict import adict

from src.types import Node
import src.cfg.access_property

BEGIN = 'BEGIN'
END = 'END'


@dataclass
class ASTNodeWrapper:
    ast_node: Node | dict[str, Node] | List[Node]  # AST dict (from json) having at least 'type' and 'id' keys.
    parent: Self | None = None  # parent node that sees this node as a child.
    children: Dict[str, Self] | List[Self] | None = None
    related: Dict[str, Self] | None = None
    metadata: adict = field(default_factory=adict)

    def get(self, role: str, identification: dict = None, previous_action_data: Self = None) -> Self | None:
        return access_property.get(self, role, identification, previous_action_data)


# Define dataclasses matching the constructs structure
@dataclass
class ActionSpec:
    # name: str
    role: str
    kind: str = ''
    generalization: str | None = None  # general role
    effects: Dict[str, Any] = field(default_factory=dict)
    identification: Dict[str, Any] = field(default_factory=dict)  # Fields: property (str), role_in_list (=> first_in_list | next_in_list), origin (=> previous | parent), property_path (=> ex. 'branches / [0] / cond' , '^ / [next] / cond' , '^ / body', etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def find_node_data(self, wrapped_ast: ASTNodeWrapper, previous_action_data: ASTNodeWrapper=None) -> ASTNodeWrapper | None:
        """ Extracts data according to requested method of access. """
        if self.role == END:  ### in (BEGIN, END):
            # the construction itself should be returned as data for END
            return wrapped_ast

        return wrapped_ast.get(self.role, self.identification, previous_action_data)


@dataclass
class TransitionSpec:
    from_: Optional[str] = None
    to_: Optional[str] = None
    to_after_last: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    effects: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConstructSpec:
    name: str
    actions: Dict[str, ActionSpec] = field(default_factory=dict)
    transitions: List[TransitionSpec] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for b in (BEGIN, END):
            self.actions[b] = ActionSpec(role=b, kind=b)

    def find_transitions_from_action(self, action: ActionSpec) -> List[TransitionSpec]:
        roles = (action.role, action.generalization)
        return [tr
                for tr in self.transitions
                if tr.from_ in roles]

    # def find_transition_from_action(self, action: ActionSpec) -> TransitionSpec | None:
    #     for role in (action.role, action.generalization):
    #         if role:
    #             tr = next((tr for tr in self.transitions if tr.from_ == role), None)
    #             if tr:
    #                 return tr
    #     # nothing found
    #     return None
    #
    def find_target_action_for_transition(
            self,
            tr: TransitionSpec,
            wrapped_ast: ASTNodeWrapper,
            previous_wrapped_ast: ASTNodeWrapper =None
    ) -> tuple[ActionSpec, ASTNodeWrapper, bool] | None:
        """  Returns related action, node data for it, and a flag:
            True: main output used, False: `to_after_last` output used.
        """
        while True:
            for target_role in (tr.to_, tr.to_after_last):
                if target_role:
                    action = self.actions[target_role]
                    target_wrapped_ast = action.find_node_data(wrapped_ast, previous_wrapped_ast)
                    if target_wrapped_ast:
                        return action, target_wrapped_ast, (target_role == tr.to_)

            # for cases where target is absent in AST, search further along transition chain
            # TODO: use assumed value of condition & more heuristics.
            primary_out = tr.to_
            trs = self.find_transitions_from_action(self.actions[primary_out])
            if not trs:
                break
            tr = trs[0]
            # not really good to just take the first.. TODO

        # nothing found
        raise ValueError([tr.from_, tr.to_, tr.to_after_last, wrapped_ast, previous_wrapped_ast])
        # return None


def load_constructs(path="./constructs.yml", debug=False):
    """ Load constructs.yml """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found. Please upload constructs.yml to /mnt/data.")

    with open(path, "r", encoding="utf-8") as f:
        raw_yaml = f.read()

    constructs_raw = yaml.safe_load(raw_yaml)
    del raw_yaml
    # return constructs_raw

    # Parse constructs into dataclasses
    constructs = {}
    for cname, cbody in constructs_raw.items():
        cs = ConstructSpec(name=cname)
        # read actions
        actions = cbody.pop("actions", None) or cbody.get("nodes") or []
        for abody in actions:
            # kind = abody.get("kind", "atom")
            role = abody.get("role", "component")
            name = role
            a = ActionSpec(**abody)
            cs.actions[name] = a
        # read transitions
        cs.transitions = []
        t: dict
        for t in cbody.pop("transitions", None) or []:
            t['from_'] = t.pop("from")  # rename attributes
            t['to_'] = t.pop("to")
            ts = TransitionSpec(**t)
            cs.transitions.append(ts)
        cs.metadata |= cbody  # all remaining data

        constructs[cname] = cs

    if debug:
        print("Loaded constructs (summary):")
        for k,v in constructs.items():
            print("-", k, ": actions:", ', '.join(a.role for a in v.actions.values()) or 'none')
            print("   \\ transitions:", ', '.join(f'{t.from_} -> {t.to_}' for t in v.transitions) or 'none')

    return constructs

# CFG classes implemented using constructs.

class IDGen:
    def __init__(self):
        self._c = itertools.count(1)
    def next(self, prefix="id"):
        return f"{prefix}_{next(self._c)}"

idgen = IDGen()

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


# ---------- CFGBuilder ----------
class CFGBuilder:
    def __init__(self, constructs_map: Dict[str, ConstructSpec]):
        self.constructs = constructs_map

    def find_construct_for_astnode(self, ast_node_wrapper: ASTNodeWrapper) -> Optional[ConstructSpec]:
        v = ast_node_wrapper.ast_node
        if isinstance(v, dict):
            node_type = v.get("type")
            for construct in self.constructs.values():
                if construct.metadata.get('ast_node') == node_type:
                    return construct
            ###
            print(f'Note: no construct found for ast_node {node_type=}')
            ###
        return None

    def make_cfg_for_ast(self, wrapped_ast: ASTNodeWrapper) -> CFG:
        construct = self.find_construct_for_astnode(wrapped_ast)
        if construct:
            return self.make_cfg_for_construct(construct, wrapped_ast)
        # fallback empty
        cfg = CFG("atom")
        cfg.connect(cfg.begin_node, cfg.end_node)
        return cfg

    def make_cfg_for_construct(self, construct: ConstructSpec, wrapped_ast: ASTNodeWrapper) -> CFG:
        """ Предполагается, что CFG для подчинённых узлов уже подготовлены и готовы быть встроены в новый. -- будут созданы рекурсивно. """
        ast_node = wrapped_ast.ast_node
        cfg_name = ast_node['type'] if 'type' in ast_node else str(ast_node)
        cfg = CFG(cfg_name)

        # Добавить метаданные: алгоритмическая конструкция и узел AST
        for node in (cfg.begin_node, cfg.end_node):
            node.metadata.abstract_construct = construct
            node.metadata.wrapped_ast = wrapped_ast

        # Применить все переходы, попутно создавая узлы,
        # c учётом множественности и повторения ...

        unprocessed_pool = [cfg.begin_node]
        processed_ids = set()

        while unprocessed_pool:
            node = unprocessed_pool.pop()
            if node.id in processed_ids:
                continue
            processed_ids.add(node.id)

            role = node.role
            # Построить выходящие переходы
            action = construct.actions[role]
            outgoing_transitions = construct.find_transitions_from_action(action)
            if not outgoing_transitions:
                # no outgoing transitions: ensure it's END
                assert role == END, f'{construct.name=} has no outgoing transitions for {role=}, and this is not END'
            for tr in outgoing_transitions:
                # resolve target action
                target_action_data_primary = construct.find_target_action_for_transition(
                    tr, wrapped_ast,
                    node.metadata.wrapped_ast)
                assert target_action_data_primary, (action, wrapped_ast)

                target_action, next_wrapped_ast, primary = target_action_data_primary

                # insert subgraph, only for compound actions
                subgraph = self.make_cfg_for_ast(next_wrapped_ast) if target_action.kind == 'compound' else None

                node23 = cfg.add_node(
                    kind=target_action.kind,
                    role=target_action.role,
                    metadata=adict(
                        abstract_construct=target_action,
                        wrapped_ast=next_wrapped_ast,
                        primary=primary ,
                    ),
                    subgraph=subgraph
                )
                # Make a pair: bounds of a compound or an atom (the same node if it's an atom)
                node_pair: tuple[Node, Node] = (node23 if isinstance(node23, tuple) else (node23, node23))

                # connect along the transition found
                cfg.connect(node, node_pair[0], metadata=adict(
                    abstract_construct=tr,
                    is_after_last = not primary,
                ))

                # последний узел (выходной) добавить в пул необработанных
                next_node = node_pair[1]
                if next_node.id not in processed_ids:
                    unprocessed_pool.append(next_node)
            # end of for.
        return cfg
