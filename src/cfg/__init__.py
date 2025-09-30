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


# Build a small demo using constructs: assume constructs.yml defines an "atom" and "sequence" constructs.
# We will create a sequence of actions where one action is a subgraph (Call) and should be inlined seamlessly.

# cfg_main = CFG("main")

# # Create a start atom
# start = cfg_main.create(kind="entry", role="entry")
# a1 = cfg_main.create(kind="atom", role="sequence_element", effects={"name":"A1"})
# # create a subgraph for a call (simulate building via builder)
# sub = CFG("sub_call")
# s_entry = sub.create(kind="entry", role="entry")
# s_call = sub.create(kind="call", role="func_call", effects={"func":"g"})
# s_exit = sub.create(kind="exit", role="exit")
# sub.connect(s_entry, s_call)
# sub.connect(s_call, s_exit)
# # Now create node in main that wraps this subgraph as atomic
# wrap = cfg_main.create(kind="subgraph_wrapper", role="sequence_element", subgraph=sub)
# a2 = cfg_main.create(kind="atom", role="sequence_element", effects={"name":"A2"})
# end = cfg_main.create(kind="exit", role="exit")
#
# # connect sequence: start -> a1 -> wrap -> a2 -> end
# cfg_main.connect(start, a1)
# cfg_main.connect(a1, wrap)
# cfg_main.connect(wrap, a2)
# cfg_main.connect(a2, end)
#
# print("\nBefore inlining:")
# cfg_main.debug()
#
# cfg_main.inline_subgraphs()
#
# print("\nAfter inlining:")
# cfg_main.debug()
#
# # Show constructs_raw head for user's info
# print("\nconstructs.yml head (first 2000 chars):\n")
# print(raw_yaml[:2000])


# cfg_builder.py
# ---------- парсер constructs.yml -> внутренние структуры ----------


# ---------- CFG structures ----------

# @dataclass
# class Node:
#     id: str
#     kind: str
#     role: Optional[str] = None
#     attrs: Dict[str, Any] = field(default_factory=dict)
#
# @dataclass
# class Edge:
#     src: str
#     dst: str
#     cond: Optional[Dict[str, Any]] = None
#     metadata: Dict[str, Any] = field(default_factory=dict)

class CFG_gpt:
    def __init__(self, name="cfg"):
        self.name = name
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._idc = itertools.count(1)
    def new_id(self, prefix="n"):
        return f"{prefix}_{next(self._idc)}"
    def add_node(self, kind, role=None, attrs=None):
        nid = self.new_id(kind)
        node = Node(id=nid, kind=kind, role=role, attrs=attrs or {})
        self.nodes[nid] = node
        return node
    def add_edge(self, src, dst, cond=None, metadata=None):
        src_id = src.id if isinstance(src, Node) else src
        dst_id = dst.id if isinstance(dst, Node) else dst
        e = Edge(src=src_id, dst=dst_id, cond=cond, metadata=metadata or {})
        self.edges.append(e)
        return e
    def merge(self, other: "CFG") -> Tuple[Dict[str,str], str, str]:
        id_map = {}
        entry_old = None; exit_old = None
        for oid, onode in other.nodes.items():
            nid = self.new_id(onode.kind)
            id_map[oid] = nid
            self.nodes[nid] = Node(id=nid, kind=onode.kind, role=onode.role, attrs=copy.deepcopy(onode.attrs))
            if onode.role == "BEGIN": entry_old = oid
            if onode.role == "END": exit_old = oid
        for e in other.edges:
            self.edges.append(Edge(src=id_map[e.src], dst=id_map[e.dst], cond=copy.deepcopy(e.cond), metadata=copy.deepcopy(e.metadata)))
        entry_new = id_map[entry_old] if entry_old else None
        exit_new = id_map[exit_old] if exit_old else None
        return id_map, entry_new, exit_new

# ---------- CFGBuilder ----------
class CFGBuilder_gpt:
    def __init__(self, constructs_map: Dict[str, ConstructSpec]):
        self.constructs = constructs_map

    def find_construct_for_astnode(self, ast_node_wrapper: ASTNodeWrapper) -> Optional[ConstructSpec]:
        v = ast_node_wrapper.ast_node
        if isinstance(v, dict):
            node_type = v.get("type")
            for cs in self.constructs.values():
                if cs.ast_node and cs.ast_node == node_type:
                    return cs
            ###
            print(f'Note: no construct found for ast_node {node_type=}')
            ###
        return None

    def make_cfg_for_construct(self, node_wrapper: ASTNodeWrapper, construct: ConstructSpec) -> CFG:
        cfg = CFG(name=f"construct_{construct.name}")
        begin = cfg.begin_node
        end = cfg.end_node
        action_nodes_map: Dict[str, List[str]] = {}

        for action_name, action in construct.actions.items():
            role = action.role
            kind = action.kind
            identification = action.identification or {}
            # prop = identification.get("property") or role
            # prop_path = identification.get("property_path")
            # identification = {}
            # if prop_path:
            #     identification['property_path'] = prop_path
            # else:
            #     identification['property'] = prop
            #     if action.raw.get("identified_by"):
            #         identification['origin'] = action.raw.get("identified_by")
            #     if action.raw.get("role_in_list"):
            #         identification['role_in_list'] = action.raw.get("role_in_list")

            fetched = node_wrapper.get(role, identification=identification)
            nodes_for_action: List[str] = []
            if fetched is None:
                action_nodes_map[action_name] = []
                continue

            if isinstance(fetched.ast_node, list):
                # Список: Пере-заполнить массив children обёртками и создать узлы в CFG
                if fetched.children is None or not isinstance(fetched.children, list):
                    fetched.children = [None]*len(fetched.ast_node)
                for idx, elem in enumerate(fetched.ast_node):
                    if fetched.children[idx] is None:
                        fetched.children[idx] = ASTNodeWrapper(elem, parent=fetched)
                    child_wrapper = fetched.children[idx]
                    if kind == "compound":  # or (action.generalization=="branch" and action.kind=="compound"):
                        subconstruct = self.find_construct_for_astnode(child_wrapper)
                        if subconstruct:
                            subcfg = self.make_cfg_for_construct(child_wrapper, subconstruct)
                            idmap, entry_new, exit_new = cfg.add_node(kind, role, {
                                "ast": child_wrapper,
                                "abstraction": action,
                            }, subcfg)
                            # idmap, entry_new, exit_new = cfg.merge(subcfg)
                            # we represent the action by its entry node (transitions target entry),
                            # exit node is available via exit_new in attrs if needed later
                            nodes_for_action.append(entry_new)
                        else:
                            an = cfg.add_node(kind="atom", role=role, metadata={"ast": child_wrapper})
                            nodes_for_action.append(an.id)
                    else:
                        an = cfg.add_node(kind=kind, role=role, metadata={"ast": child_wrapper})
                        nodes_for_action.append(an.id)
            else:
                # Словарь в качестве узла AST
                child_wrapper = fetched
                if kind == "compound":  ### or action.kind=="compound":
                    subconstruct = self.find_construct_for_astnode(child_wrapper)
                    if subconstruct:
                        subcfg = self.make_cfg_for_construct(child_wrapper, subconstruct)
                        idmap, entry_new, exit_new = cfg.merge(subcfg)
                        nodes_for_action.append(entry_new)
                    else:
                        an = cfg.add_node(kind="atom", role=role, attrs={"source": child_wrapper.ast_node})
                        nodes_for_action.append(an.id)
                else:
                    an = cfg.add_node(kind=kind, role=role, attrs={"source": child_wrapper.ast_node})
                    nodes_for_action.append(an.id)

            action_nodes_map[action_name] = nodes_for_action

        # Create transitions
        for tr in construct.transitions:
            trr = tr.raw
            fr = trr.get("from")
            to = trr.get("to") or trr.get("to_after_last") or trr.get("to_when_absent") or trr.get("to_after")
            cond = None
            if "condition_value" in trr:
                cond = {"on_expr_value": trr["condition_value"]}
            metadata = {}
            if "effects" in trr:
                metadata["effects"] = trr["effects"]

            src_ids = []
            if fr in ("BEGIN","start"):
                src_ids = [begin.id]
            elif fr in ("END",):
                src_ids = [end.id]
            else:
                for action_name, action in construct.actions.items():
                    if action_name == fr or action.raw.get("generalization")==fr or action.raw.get("role")==fr:
                        src_ids.extend(action_nodes_map.get(action_name, []))

            dst_ids = []
            if to in ("END","END_LAST"):
                dst_ids = [end.id]
            elif to in ("BEGIN",):
                dst_ids = [begin.id]
            else:
                for action_name, action in construct.actions.items():
                    if action_name == to or action.raw.get("generalization")==to or action.raw.get("role")==to:
                        dst_ids.extend(action_nodes_map.get(action_name, []))

            if not dst_ids and ("to_after_last" in trr or trr.get("to_after")):
                dst_ids = [end.id]
            if not dst_ids and ("to_when_absent" in trr):
                dst_ids = [end.id]

            for s in src_ids:
                for d in dst_ids:
                    cfg.add_edge(s, d, cond=cond, metadata=metadata)

        # If no transition produced, create simple linear chain (fallback)
        if not cfg.edges:
            prev = begin
            for action_name in construct.actions.keys():
                nodes = action_nodes_map.get(action_name, [])
                for nid in nodes:
                    cfg.add_edge(prev.id, nid)
                    prev = cfg.nodes[nid]
            cfg.add_edge(prev.id, end.id)

        return cfg

    def build(self, ast_root: ASTNodeWrapper) -> CFG:
        cs = self.find_construct_for_astnode(ast_root)
        if cs:
            return self.make_cfg_for_construct(ast_root, cs)
        # fallback empty
        cfg = CFG("fallback")
        b = cfg.add_node("BEGIN", role="BEGIN")
        e = cfg.add_node("END", role="END")
        cfg.add_edge(b.id, e.id)
        return cfg

