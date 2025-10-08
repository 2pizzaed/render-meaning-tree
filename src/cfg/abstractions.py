# Define dataclasses matching the constructs structure

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

import yaml

import src.cfg.ast_wrapper as aw
from src.common_utils import DictLikeDataclass, SelfValidatedEnum


BEGIN = 'BEGIN'
END = 'END'


class OriginType(SelfValidatedEnum):
    """Origin types for identification"""
    PARENT = "parent"
    PREVIOUS = "previous"


class RoleInListType(SelfValidatedEnum):
    """Role in list types for identification"""
    FIRST_IN_LIST = "first_in_list"
    NEXT_IN_LIST = "next_in_list"


class InterruptionType(SelfValidatedEnum):
    """Interruption types for effects"""
    BREAK = "break"
    CONTINUE = "continue"
    RETURN = "return"
    EXCEPTION = "exception"


class CallStackAction(SelfValidatedEnum):
    """Call stack actions for effects"""
    ADD_FRAME = "add_frame"
    DROP_FRAME = "drop_frame"


class ConditionValue(SelfValidatedEnum):
    """Condition values for constraints"""
    TRUE = True
    FALSE = False


class InterruptionMode(SelfValidatedEnum):
    """Interruption modes for constraints"""
    EXCEPTION = "exception"
    ANY = "any"


@dataclass
class Effects(DictLikeDataclass):
    """Effects that can be applied to actions or transitions"""
    interruption_stop: Optional[InterruptionType] = None
    interruption_start: Optional[InterruptionType] = None
    call_stack: Optional[CallStackAction] = None


@dataclass
class Identification(DictLikeDataclass):
    """Identification specification for finding nodes in AST"""
    origin: Optional[OriginType] = None
    property: Optional[str] = None
    property_path: Optional[str] = None
    role_in_list: Optional[RoleInListType] = None


@dataclass
class Behaviour(DictLikeDataclass):
    """Behaviour for actions"""
    assumed_value: Optional[bool] = None
    # # Additional fields can be added as needed
    # custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class Constraints(DictLikeDataclass):
    """Constraints for transitions"""
    condition_value: Optional[ConditionValue] = None
    interruption_mode: Optional[InterruptionMode] = None
    # # Additional constraints can be added as needed
    # custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionSpec(DictLikeDataclass):
    # name: str
    role: str
    kind: str = ''
    generalization: str | None = None  # general role
    effects: List[Effects] = field(default_factory=Effects)
    identification: Identification = field(default_factory=Identification)
    behaviour: Behaviour = field(default_factory=Behaviour)

    def find_node_data(self, wrapped_ast: 'aw.ASTNodeWrapper', previous_action_data: 'aw.ASTNodeWrapper'=None) -> (
            'aw.ASTNodeWrapper | None'):
        """ Extracts data according to requested method of access. """
        if self.role == END:  ### in (BEGIN, END):
            # the construction itself should be returned as data for END
            return wrapped_ast

        return wrapped_ast.get(self.role, self.identification, previous_action_data)


@dataclass
class TransitionSpec(DictLikeDataclass):
    from_: Optional[str] = None
    to: Optional[str] = None
    to_when_absent: Optional[str] = None
    constraints: Optional[Constraints] = None
    effects: List[Effects] = field(default_factory=Effects)
    # metadata: Metadata = field(default_factory=Metadata)


@dataclass
class ConstructSpec(DictLikeDataclass):
    name: str
    kind: str = None
    ast_node: str = None
    actions: list[ActionSpec] = field(default_factory=list)
    id2action: dict[str, ActionSpec] = None
    transitions: list[TransitionSpec] = field(default_factory=list)
    effects: List[Effects] = field(default_factory=Effects)
    # metadata: Metadata = field(default_factory=Metadata)

    def __post_init__(self):
        # Add BEGIN and END actions if not present
        for b in (BEGIN, END):
            if not any(action.role == b for action in self.actions):
                self.actions.append(ActionSpec(role=b, kind=b))

        self.id2action = {
            action.role: action
            for action in self.actions
        }

    def find_transitions_from_action(self, action: ActionSpec) -> list[TransitionSpec]:
        roles = (action.role, action.generalization)
        return [tr
                for tr in self.transitions
                if tr.from_ in roles]

    def find_target_action_for_transition(
            self,
            tr: TransitionSpec,
            wrapped_ast: 'aw.ASTNodeWrapper',
            previous_wrapped_ast: 'aw.ASTNodeWrapper' =None,
            transition_chain: list['TransitionSpec'] = None
    ) -> tuple[ActionSpec, 'aw.ASTNodeWrapper', bool, list['TransitionSpec']] | None:
        """  Returns related action, node data for it, a flag, and the transition chain:
            True: main output used, False: `to_when_absent` output used.
            transition_chain: list of transitions that led to the target action.
        """
        if transition_chain is None:
            transition_chain = []
        
        current_chain = transition_chain + [tr]
        
        while True:
            for target_role in (tr.to, tr.to_when_absent):
                if target_role:
                    action = self.id2action.get(target_role)
                    if action:
                        target_wrapped_ast = action.find_node_data(wrapped_ast, previous_wrapped_ast)
                        if target_wrapped_ast:
                            return action, target_wrapped_ast, (target_role == tr.to), current_chain

            # for cases where target is absent in AST, search further along transition chain
            # TODO: use assumed value of condition & more heuristics.
            primary_out = tr.to
            primary_action = self.id2action.get(primary_out)
            if not primary_action:
                break
            trs = self.find_transitions_from_action(primary_action)
            if not trs:
                break
            tr = trs[0]
            # not really good to just take the first.. TODO
            current_chain.append(tr)

        # nothing found
        raise ValueError([tr.from_, tr.to, tr.to_when_absent, wrapped_ast, previous_wrapped_ast])
        # return None





def load_constructs(path="./constructs.yml", debug=False):
    """ Load constructs.yml using DictLikeDataclass """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found. Please upload constructs.yml to /mnt/data.")

    with open(path, "r", encoding="utf-8") as f:
        raw_yaml = f.read()

    constructs_raw = yaml.safe_load(raw_yaml)
    del raw_yaml

    # Parse constructs into dataclasses using DictLikeDataclass
    constructs = {}
    for cname, cbody in constructs_raw.items():
        # Create ConstructSpec using DictLikeDataclass.make
        cs = ConstructSpec.make({"name": cname, **cbody})
        
        constructs[cname] = cs

    if debug:
        print("Loaded constructs (summary):")
        for k, v in constructs.items():
            print("-", k, ": actions:", ', '.join(a.role for a in v.actions) or 'none')
            print("   \\ transitions:", ', '.join(f'{t.from_} -> {t.to}' for t in v.transitions) or 'none')

    return constructs


def load_ast_from_json(path="ast.json"):
    """Load AST from JSON file using DictLikeDataclass"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found.")
    
    with open(path, "r", encoding="utf-8") as f:
        ast_data = json.load(f)
    
    # Create a generic AST node dataclass for parsing
    @dataclass
    class ASTNode(DictLikeDataclass):
        type: str
        id: Optional[int] = None
        name: Optional[str] = None
        value: Optional[Any] = None
        body: Optional[List[Dict[str, Any]]] = None
        branches: Optional[List[Dict[str, Any]]] = None
        condition: Optional[Dict[str, Any]] = None
        target: Optional[Dict[str, Any]] = None
        left_operand: Optional[Dict[str, Any]] = None
        right_operand: Optional[Dict[str, Any]] = None
        operand: Optional[Dict[str, Any]] = None
        statements: Optional[List[Dict[str, Any]]] = None
        elseBranch: Optional[Dict[str, Any]] = None
        repr: Optional[str] = None
    
    return ASTNode.make(ast_data)
