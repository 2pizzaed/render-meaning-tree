# Define dataclasses matching the constructs structure

import os
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml

from src.cfg.cfg import END, BEGIN
from src.cfg.ast_wrapper import ASTNodeWrapper


@dataclass
class ActionSpec:
    # name: str
    role: str
    kind: str = ''
    generalization: str | None = None  # general role
    effects: dict[str, Any] = field(default_factory=dict)
    identification: dict[str, Any] = field(default_factory=dict)  # Fields: property (str), role_in_list (=> first_in_list | next_in_list), origin (=> previous | parent), property_path (=> ex. 'branches / [0] / cond' , '^ / [next] / cond' , '^ / body', etc.)
    metadata: dict[str, Any] = field(default_factory=dict)

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
    constraints: Optional[dict[str, Any]] = None
    effects: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstructSpec:
    name: str
    actions: dict[str, ActionSpec] = field(default_factory=dict)
    transitions: list[TransitionSpec] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

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
