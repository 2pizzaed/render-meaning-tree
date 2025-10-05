# Define dataclasses matching the constructs structure

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import yaml

from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.cfg import END, BEGIN


class DictLikeDataclass:
    """ Mixins for dataclasses to be used as dict """
    __getitem__ = getattr
    __setitem__ = object.__setattr__
    get = getattr


class OriginType(Enum):
    """Origin types for identification"""
    PARENT = "parent"
    PREVIOUS = "previous"


class RoleInListType(Enum):
    """Role in list types for identification"""
    FIRST_IN_LIST = "first_in_list"
    NEXT_IN_LIST = "next_in_list"


class InterruptionType(Enum):
    """Interruption types for effects"""
    BREAK = "break"
    CONTINUE = "continue"
    RETURN = "return"
    EXCEPTION = "exception"


class CallStackAction(Enum):
    """Call stack actions for effects"""
    ADD_FRAME = "add_frame"
    DROP_FRAME = "drop_frame"


class ConditionValue(Enum):
    """Condition values for constraints"""
    TRUE = True
    FALSE = False


class InterruptionMode(Enum):
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
class Metadata(DictLikeDataclass):
    """General metadata for actions, transitions, and nodes"""
    assumed_value: Optional[bool] = None
    ast_node: Optional[str] = None
    abstract_action: Optional['ActionSpec'] = None
    wrapped_ast: Optional[ASTNodeWrapper] = None
    primary: Optional[bool] = None
    abstract_transition: Optional['TransitionSpec'] = None
    is_after_last: Optional[bool] = None
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
class ActionSpec:
    # name: str
    role: str
    kind: str = ''
    generalization: str | None = None  # general role
    effects: Effects = field(default_factory=Effects)
    identification: Identification = field(default_factory=Identification)
    metadata: Metadata = field(default_factory=Metadata)

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
    to_when_absent: Optional[str] = None
    constraints: Optional[Constraints] = None
    effects: Effects = field(default_factory=Effects)
    metadata: Metadata = field(default_factory=Metadata)


@dataclass
class ConstructSpec:
    name: str
    actions: dict[str, ActionSpec] = field(default_factory=dict)
    transitions: list[TransitionSpec] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)

    def __post_init__(self):
        for b in (BEGIN, END):
            self.actions[b] = ActionSpec(role=b, kind=b)

    def find_transitions_from_action(self, action: ActionSpec) -> list[TransitionSpec]:
        roles = (action.role, action.generalization)
        return [tr
                for tr in self.transitions
                if tr.from_ in roles]

    def find_target_action_for_transition(
            self,
            tr: TransitionSpec,
            wrapped_ast: ASTNodeWrapper,
            previous_wrapped_ast: ASTNodeWrapper =None
    ) -> tuple[ActionSpec, ASTNodeWrapper, bool] | None:
        """  Returns related action, node data for it, and a flag:
            True: main output used, False: `to_when_absent` output used.
        """
        while True:
            for target_role in (tr.to_, tr.to_when_absent):
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
        raise ValueError([tr.from_, tr.to_, tr.to_when_absent, wrapped_ast, previous_wrapped_ast])
        # return None


def _parse_effects(effects_data: list | dict | None) -> Effects:
    """Parse effects data from YAML into Effects dataclass"""
    if not effects_data:
        return Effects()
    
    effects = Effects()
    
    if isinstance(effects_data, list):
        # Handle list format like: [{"interruption_stop": "break"}]
        for effect_item in effects_data:
            if isinstance(effect_item, dict):
                for key, value in effect_item.items():
                    if key == "interruption_stop":
                        effects.interruption_stop = InterruptionType(value)
                    elif key == "interruption_start":
                        effects.interruption_start = InterruptionType(value)
                    elif key == "call_stack":
                        effects.call_stack = CallStackAction(value)
                    else:
                        effects.custom[key] = value
    elif isinstance(effects_data, dict):
        # Handle dict format
        for key, value in effects_data.items():
            if key == "interruption_stop":
                effects.interruption_stop = InterruptionType(value)
            elif key == "interruption_start":
                effects.interruption_start = InterruptionType(value)
            elif key == "call_stack":
                effects.call_stack = CallStackAction(value)
            else:
                effects.custom[key] = value
    
    return effects


def _parse_identification(ident_data: dict | None) -> Identification:
    """Parse identification data from YAML into Identification dataclass"""
    if not ident_data:
        return Identification()
    
    ident = Identification()
    
    if "origin" in ident_data:
        try:
            ident.origin = OriginType(ident_data["origin"])
        except ValueError:
            ident.custom["origin"] = ident_data["origin"]
    
    if "property" in ident_data:
        ident.property = ident_data["property"]
    
    if "property_path" in ident_data:
        ident.property_path = ident_data["property_path"]
    
    if "role_in_list" in ident_data:
        try:
            ident.role_in_list = RoleInListType(ident_data["role_in_list"])
        except ValueError:
            ident.custom["role_in_list"] = ident_data["role_in_list"]
    
    # Store any additional fields in custom
    for key, value in ident_data.items():
        if key not in ["origin", "property", "property_path", "role_in_list"]:
            ident.custom[key] = value
    
    return ident


def _parse_constraints(constraints_data: dict | None) -> Constraints:
    """Parse constraints data from YAML into Constraints dataclass"""
    if not constraints_data:
        return Constraints()
    
    constraints = Constraints()
    
    if "condition_value" in constraints_data:
        try:
            constraints.condition_value = ConditionValue(constraints_data["condition_value"])
        except ValueError:
            constraints.custom["condition_value"] = constraints_data["condition_value"]
    
    if "interruption_mode" in constraints_data:
        try:
            constraints.interruption_mode = InterruptionMode(constraints_data["interruption_mode"])
        except ValueError:
            constraints.custom["interruption_mode"] = constraints_data["interruption_mode"]
    
    # Store any additional fields in custom
    for key, value in constraints_data.items():
        if key not in ["condition_value", "interruption_mode"]:
            constraints.custom[key] = value
    
    return constraints


def _parse_metadata(metadata_data: dict | None) -> Metadata:
    """Parse metadata data from YAML into Metadata dataclass"""
    if not metadata_data:
        return Metadata()
    
    metadata = Metadata()
    
    if "assumed_value" in metadata_data:
        metadata.assumed_value = metadata_data["assumed_value"]
    
    if "ast_node" in metadata_data:
        metadata.ast_node = metadata_data["ast_node"]
    
    # Store any additional fields in custom
    for key, value in metadata_data.items():
        if key not in ["assumed_value", "ast_node"]:
            metadata.custom[key] = value
    
    return metadata


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
        # Parse metadata first
        metadata = _parse_metadata(cbody)
        
        cs = ConstructSpec(name=cname, metadata=metadata)
        
        # read actions
        actions = cbody.pop("actions", None) or cbody.get("nodes") or []
        for abody in actions:
            # Parse action fields
            action_effects = _parse_effects(abody.pop("effects", None))
            action_identification = _parse_identification(abody.pop("identification", None))
            action_metadata = _parse_metadata(abody.pop("metadata", None))
            
            # Create ActionSpec with parsed fields
            role = abody.get("role", "component")
            name = role
            a = ActionSpec(
                role=role,
                kind=abody.get("kind", "atom"),
                generalization=abody.get("generalization"),
                effects=action_effects,
                identification=action_identification,
                metadata=action_metadata
            )
            cs.actions[name] = a
        
        # read transitions
        cs.transitions = []
        for t in cbody.pop("transitions", None) or []:
            # Parse transition fields
            transition_constraints = _parse_constraints(t.pop("constraints", None))
            transition_effects = _parse_effects(t.pop("effects", None))
            transition_metadata = _parse_metadata(t.pop("metadata", None))
            
            # Create TransitionSpec with parsed fields
            ts = TransitionSpec(
                from_=t.pop("from"),
                to_=t.pop("to"),
                to_when_absent=t.get("to_when_absent"),
                constraints=transition_constraints,
                effects=transition_effects,
                metadata=transition_metadata
            )
            cs.transitions.append(ts)

        constructs[cname] = cs

    if debug:
        print("Loaded constructs (summary):")
        for k,v in constructs.items():
            print("-", k, ": actions:", ', '.join(a.role for a in v.actions.values()) or 'none')
            print("   \\ transitions:", ', '.join(f'{t.from_} -> {t.to_}' for t in v.transitions) or 'none')

    return constructs
