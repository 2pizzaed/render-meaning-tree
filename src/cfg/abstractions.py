# Define dataclasses matching the constructs structure

import os
from dataclasses import dataclass, field
from typing import Optional, Self

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

class ActionKind(SelfValidatedEnum):
    """Single values associated with kind of ActionSpec """
    # common useful
    CONDITION = "condition"
    BLOCK = "block"
    # constructs known so far
    SEQUENCE = "sequence"
    ALTERNATIVE = "alternative"
    LOOP = "loop"
    NOOP = "noop"
    CALL = "call"
    TRY = "try"
    # basic types
    COMPOUND = "compound"
    INLINE = "inline"
    # for usage as constraint
    ANY = "any"


class KindChain:
    """Dot-chained names each of which can be queried separately"""
    chain: list[str]

    def __init__(self, chain: str | list[str] | Self = '', sep='.'):
        if isinstance(chain, str):
            self.chain = chain.split(sep) if chain else []
        elif isinstance(chain, list):
            self.chain = chain
        elif isinstance(chain, type(self)):
            self.chain = chain.chain
        else:
            raise TypeError(f'KindChain\'s "chain" must be str or list, not {type(chain).__name__}')

    def __contains__(self, item):
        return item in self.chain
    has = __contains__

    def is_subset_of(self, other: Self | list[Self]) -> bool:
        return all((item in other) for item in self.chain)

    def to_enums(self) -> list[ActionKind]:
        """ to list of ActionKind instances, filtered & ordered by the enum. """
        known_kinds = []
        # перебор в порядке определения членов ActionKind
        for kind in ActionKind.__members__.values():
            if kind.value in self:
                known_kinds.append(ActionKind.lookup(kind.value))
                # known_kinds.append(ActionKind.__members__[kind])
        return known_kinds

    def __hash__(self):
        return hash(tuple(self.chain))

    def __iter__(self):
        return iter(self.chain)

    def __len__(self):
        return len(self.chain)

    def __str__(self):
        return '.'.join(self.chain)
    __repr__ = __str__


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
    role: str
    name: str = None
    kind: KindChain = KindChain()
    generalization: str | None = None  # general role
    effects: list[Effects] = field(default_factory=list)
    identification: Identification = field(default_factory=Identification)  # not exported; for CFG construction only.
    behaviour: Behaviour = field(default_factory=Behaviour)
    construct: 'ConstructSpec' = None

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
    to_when_absent: Optional[list[str] | str] = None  # Chain of fallbacks is supported as well. List is first as more specific for automatic creation/conversion.
    constraints: Optional[Constraints] = None
    effects: list[Effects] = field(default_factory=list)
    # metadata: Metadata = field(default_factory=Metadata)
    construct: 'ConstructSpec' = None

    def to_when_absent_as_list(self) -> list[str]:
        if isinstance(self.to_when_absent, list):
            return self.to_when_absent
        if self.to_when_absent:
            return [self.to_when_absent]
        return []

@dataclass

class ConstructSpec(DictLikeDataclass):
    name: str
    kind: KindChain = KindChain()
    ast_node: str | None = None
    actions: list[ActionSpec] = field(default_factory=list)
    role2action: dict[str, ActionSpec] | None = None
    transitions: list[TransitionSpec] = field(default_factory=list)
    effects: list[Effects] = field(default_factory=list)
    # metadata: Metadata = field(default_factory=Metadata)

    def __post_init__(self):
        # Add BEGIN and END actions if not present
        for b in (BEGIN, END):
            # add bounds if not defined explicitly.
            if not any(action.role == b for action in self.actions):
                self.actions.append(ActionSpec(role=b, kind=self.kind))

        # re-index actions by role,
        # & set full name based on construct name
        self.role2action = {}
        for action in self.actions:
            self.role2action[action.role] = action
            action.name = self.name + "_" + action.role
            action.construct = self

        # Add construct's Effects to END node
        self.role2action[END].effects += self.effects

        # Bind transitions to self
        for transition in self.transitions:
            transition.construct = self

    def find_action_by_role(self, role: str) -> Optional[ActionSpec]:
        """ Only one action is mapped to a role.
        But note that several actions can have the same generalization (in this case, any is returned). """
        if role in self.role2action:
            return self.role2action[role]
        # actions = []
        for action in self.actions:
            if action.role == role or action.generalization == role:
                return action
                # actions.append(action)
        return None

    def find_transitions_from_action(self, action: ActionSpec) -> list[TransitionSpec]:
        roles = (action.role, action.generalization)
        return [tr
                for tr in self.transitions
                if tr.from_ in roles]

    def find_target_action_for_transition(
            self,
            tr: TransitionSpec,
            wrapped_ast: 'aw.ASTNodeWrapper',
            previous_wrapped_ast: 'aw.ASTNodeWrapper' = None,
    ) -> tuple[ActionSpec, 'aw.ASTNodeWrapper', bool, list['TransitionSpec']] | None:
        """  Returns related action, node data for it, a flag, and the transition chain:
            flag: True: main output used, False: `to_when_absent` output used.
            transition_chain: list of transitions that led to the target action.
        """
        current_chain = [tr]

        while True:
            for target_role in (tr.to, *tr.to_when_absent_as_list()):
                if target_role:
                    action = self.role2action.get(target_role)
                    if action:
                        target_wrapped_ast = action.find_node_data(wrapped_ast, previous_wrapped_ast)
                        if target_wrapped_ast:
                            return action, target_wrapped_ast, (target_role == tr.to), current_chain

            # for cases where target is absent in AST, search further along transition chain
            # TODO: use assumed value of condition & more heuristics.
            primary_out = tr.to
            primary_action = self.role2action.get(primary_out)
            if not primary_action:
                break
            trs = self.find_transitions_from_action(primary_action)
            if not trs:
                break
            tr = trs[0]
            # not really good to just take the first.. TODO
            if tr in current_chain:
                break  # prevent infinite looping
            current_chain.append(tr)

        # nothing found
        raise ValueError([tr.from_, tr.to, tr.to_when_absent, wrapped_ast.ast_node['id'], previous_wrapped_ast.ast_node['id']])
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


class AppearanceType(SelfValidatedEnum):
    """Show action buttons or not."""
    MANDATORY = "mandatory"
    NONE = "none"
    # OPTIONAL = "optional"


@dataclass
class AppearanceProfile(DictLikeDataclass):
    name: str
    checks: dict[KindChain, AppearanceType]

    def __post_init__(self):
        # sort checks by specificity (len of kind chain) DESC
        self.checks = dict(sorted(self.checks.items(), key=lambda kv: len(kv[0]), reverse=True))

    def get_appearance_for_kind_chain(self, chain: KindChain):
        # sort checks by specificity (len of kind chain) DESC
        for etalon_chain, appearance in self.checks.items():
            if etalon_chain.is_subset_of(chain):
                return appearance

        return AppearanceType.MANDATORY # "show" for all unknown


def load_appearance_profiles(path="./construct_appearance.yml", debug=False) -> list[AppearanceProfile]:
    """ Loads profiles of action-button appearance from file, following config.
    if `profiles_priority` is present in the file, it is used to reorder profiles.
    Otherwise, result list will contain profiles exactly in the order these written under `profiles`.
     """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found.")

    with open(path, "r", encoding="utf-8") as f:
        raw_yaml = f.read()

    profiles_data_raw = yaml.safe_load(raw_yaml)
    del raw_yaml

    # Extract profiles data and priority
    profiles_data = profiles_data_raw.get('profiles', {})
    profiles_priority = profiles_data_raw.get('profiles_priority', [])

    # Create AppearanceProfile objects
    profiles_list = []
    for profile_name, profile_checks in profiles_data.items():
        # Create AppearanceProfile using DictLikeDataclass.make
        profile = AppearanceProfile.make({
            "name": profile_name,
            "checks": profile_checks
        })
        profiles_list.append(profile)

    # Apply priority ordering if specified
    if profiles_priority:
        # Create a mapping of profile names to profiles
        profile_map = {profile.name: profile for profile in profiles_list}
        
        # Reorder according to priority
        ordered_profiles = []
        for priority_name in profiles_priority:
            if priority_name in profile_map:
                ordered_profiles.append(profile_map[priority_name])
                del profile_map[priority_name]  # Remove to avoid duplicates
        
        # Add remaining profiles not in priority list
        ordered_profiles.extend(profile_map.values())
        profiles_list = ordered_profiles

    if debug:
        print("Loaded appearance profiles:")
        for profile in profiles_list:
            print(f"- {profile.name}: {len(profile.checks)} checks")

    return profiles_list


DEFAULT_APPEARANCE_PROFILE = load_appearance_profiles()[0]
assert DEFAULT_APPEARANCE_PROFILE is not None
