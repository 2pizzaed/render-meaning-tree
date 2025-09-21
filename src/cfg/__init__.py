# Read constructs.yml from /mnt/data and build dataclasses for constructs.
# Then implement a CFG builder that loads constructs, creates dataclasses, and uses them to create handlers.
# The demo will show reading the YAML, instantiating constructs, and creating a simple CFG where
# subgraphes are inlined seamlessly when used as atomic actions in a sequence.

from dataclasses import dataclass, field
from operator import index
from typing import Dict, List, Optional, Any, Callable, Tuple, Self
import yaml
import os
import itertools

from adict import adict

from src.types import NodeType

BEGIN = 'BEGIN'
END = 'END'


@dataclass
class ASTNodeWrapper:
    value: NodeType
    children: Dict[str, Self] | List[Self] | None = None
    related: Optional[Dict[str, Self]] = None
    metadata: adict[str, Any] = field(default_factory=adict)

    def get(self, role, identification: dict = None, previous_action_data: Self = None):
        """ Extracts data according to requested method of access. """
        if not identification:
            # direct parent-based lookup
            return self.children.get(role, None)
        else:
            # identification = identification
            property_ = identification.get('property', role)
            if 'role_in_list' not in identification:
                if (origin := identification.get('origin')) and origin == 'previous':
                    # relative to recent action
                    assert previous_action_data, (self.__dict__, property_)
                    return previous_action_data.get(property_)
                else:
                    return self.children.get(property_, None)
            else:
                # introspecting list
                lst = self.children if ('property' not in identification) and isinstance(self.children, list) else self.children.get(property_)
                assert isinstance(lst, list), lst

                role_in_list = identification.get('role_in_list')
                if role_in_list == 'first_in_list':
                    # get 1st (or None)
                    return next(lst, None)
                if role_in_list == 'next_in_list':
                    # get next (or None)
                    assert previous_action_data in lst, previous_action_data
                    i = lst.index(previous_action_data)
                    i += 1  # move to next element
                    return lst[i] if i < len(lst) else None
                raise ValueError(role_in_list)


# Define dataclasses matching the constructs structure
@dataclass
class ActionSpec:
    # name: str
    role: str
    kind: str = ''
    generalization: str | None = None  # general role
    effects: Dict[str, Any] = field(default_factory=dict)
    identification: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def find_node_data(self, node_data: ASTNodeWrapper, previous_action_data: ASTNodeWrapper=None) -> ASTNodeWrapper | None:
        """ Extracts data according to requested method of access. """
        return node_data.get(self.role, self.identification, previous_action_data)
        # if not self.identification:
        #     # direct parent-based lookup
        #     return node_data.get(self.role, None)
        # else:
        #     idn = self.identification
        #     property_ = idn.get('property', self.role)
        #     if 'role_in_list' not in idn:
        #         if (origin := idn.get('origin')) and origin == 'previous':
        #             # relative to recent action
        #             assert previous_action_data, (self.__dict__, node_data)
        #             return previous_action_data.get(property_, None)
        #         else:
        #             return node_data.get(property_, None)
        #     else:
        #         # introspecting list
        #         lst = node_data if ('property' not in idn) and isinstance(node_data, list) else node_data.get(property_)
        #         assert isinstance(node_data, list), lst
        #
        #         role_in_list = idn.get('role_in_list')
        #         if role_in_list == 'first_in_list':
        #             # get 1st (or None)
        #             return next(lst, None)
        #         if role_in_list == 'next_in_list':
        #             # get next (or None)
        #             assert previous_action_data in lst, previous_action_data
        #             i = lst.index(previous_action_data)
        #             i += 1  # move to next element
        #             return lst[i] if i < len(lst) else None
        #         raise ValueError(role_in_list)


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
            node_data: ASTNodeWrapper,
            previous_action_data: ASTNodeWrapper =None
    ) -> tuple[ActionSpec, ASTNodeWrapper, bool] | None:
        """  Returns related action, node data for it, and a flag:
            True: main output used, False: `to_after_last` output used.
        """
        for target_role in (tr.to_, tr.to_after_last):
            if target_role:
                action = self.actions[target_role]
                data = action.find_node_data(node_data, previous_action_data)
                if data:
                    return action, data, (target_role == tr.to_)
        # nothing found
        raise ValueError([tr, node_data, previous_action_data])
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
            print("-", k, ": actions:", list(v.actions.keys()) or 'none')

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
    metadata: adict[str, Any] = field(default_factory=adict)
    # # If node wraps a subgraph, keep reference
    # subgraph: Optional["CFG"] = None

@dataclass
class Edge:
    src: str
    dst: str
    constraints: Optional[Dict[str, Any]] = None
    metadata: adict[str, Any] = field(default_factory=adict)

class CFG:
    def __init__(self, name="cfg"):
        self.name = name
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        # init boundaries
        self.begin_node = self.create(BEGIN, BEGIN)
        self.end_node = self.create(END, END)

    def create(self, kind: str, role: str=None, metadata: dict=None, subgraph: Self=None) -> Node | tuple[Node, Node]:
        if not subgraph:
            # Node is an atom.
            nid = idgen.next(kind)
            node = Node(id=nid, kind=kind, role=role, metadata=metadata or {})
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
            leave_node = Node(id=nid, kind=kind, role=role, metadata=metadata or {})
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
        print(f"CFG {self.name}: nodes={len(self.nodes)} edges={len(self.edges)}")
        for nid,n in self.nodes.items():
            print(" ○", nid, n.kind, n.role, )#("(subgraph)" if n.subgraph else ""))
        for e in self.edges:
            print("  ", e.src, "->", e.dst, e.constraints or "", e.metadata or "")


def make_cfg_for_construct(construct: ConstructSpec, node_data: ASTNodeWrapper) -> CFG:
    """ Предполагается, что CFG для подчинённых узлов уже подготовлены и готовы быть встроены в новый. """
    cfg_name = node_data['type'] if 'type' in node_data else str(node_data)
    cfg = CFG(cfg_name)

    for node in (cfg.begin_node, cfg.end_node):
        node.metadata.abstract_construct = construct
        node.metadata.node_data = node_data

    # Применить все переходы, попутно создавая узлы,
    # c учётом множественности и повторения ...

    unprocessed_pool = [cfg.begin_node]
    processed_set = set()

    while unprocessed_pool:
        node = unprocessed_pool.pop()
        role = node.role
        action = construct.actions[role]
        for tr in construct.find_transitions_from_action(action):
            target_action_data_primary = construct.find_target_action_for_transition(
                tr, node_data,
                node.metadata.node_data)
            if target_action_data_primary:
                target_action, data, primary = target_action_data_primary
                node23 = cfg.create(
                    kind=target_action.kind,
                    role=target_action.role,
                    metadata=adict(abstract_construct=action, node_data=data),
                    subgraph=None  ## TODO !!!
                )
                for node2 in (node23 if isinstance(node23, tuple) else (node23,)):
                    # TODO последний узел (выходной) добавить в пул необработанных !
                    ...
            ...


    ...

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
