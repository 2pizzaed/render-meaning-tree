from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.ast_managers import CodeManager
from src.model.rules import (
    ActionDeclaration,
    ConstructDeclaration,
    InterruptionType,
    TransitionDeclaration,
)
from src.types import Node


class SituationContext(Protocol):
    @property
    def code(self) -> CodeManager:
        ...

    @property
    def rules(self) -> list[ConstructDeclaration]:
        ...

    @property
    def trace_acts(self) -> list[TraceAct]:
        ...

    def get_construct_for(self, ast_id: int) -> Construct | None:
        ...

    def get_actions_for(self, ast_id: int) -> list[Action]:
        ...

    def get_related_actions(self, construct: Construct) -> list[Action]:
        ...

    def add(self, object: Any):
        ...


class OrderedChain[T](Protocol):
    @property
    def chain(self) -> list[T]:
        ...

    @property
    def chain_order(self) -> int:
        ...


@dataclass(slots=True)
class Action:
    ast_id: int | None
    values: list[bool]
    rule: ActionDeclaration
    parent: Construct
    owner: SituationContext

    @property
    def chain(self) -> list[Action]:
        return self.owner.get_related_actions(self.parent)

    @property
    def ast_node(self) -> Node | None:
        return self.owner.code.get_node_by_id(self.ast_id) \
            if self.ast_id is not None else None

    def is_empty(self) -> bool:
        return self.ast_id == -1

    def possible_transitions(self) -> list[TransitionDeclaration]:
        return self.parent.rule.compiled_transitions_for_action(self.rule)

    @property
    def chain_order(self) -> int:
        return _chain_order(self.chain, self)

    def is_atomic(self) -> bool:
        return self.expands_to() is None

    def expands_to(self) -> Construct | None:
        return self.owner.get_construct_for(self.ast_id) \
            if self.ast_id is not None else None


@dataclass(slots=True)
class Construct:
    parent: Construct | None
    ast_id: int
    rule: ConstructDeclaration
    owner: SituationContext

    def __post_init__(self):
        self.begin_action()
        self.end_action()

    @property
    def ast_node(self) -> Node:
        result = self.owner.code.get_node_by_id(self.ast_id)
        if not result:
            raise ValueError(f"AST node with id {self.ast_id} not found")
        return result

    @property
    def actions(self) -> list[Action]:
        return self.owner.get_related_actions(self)

    def action_by_role(self, role: str) -> list[Action]:
        return [action for action in self.actions if action.rule.role == role]

    def begin_action(self) -> Action:
        return self._ensure_boundary_action("BEGIN")

    def end_action(self) -> Action:
        return self._ensure_boundary_action("END")

    def _ensure_boundary_action(self, role: str) -> Action:
        existing = self.action_by_role(role)
        if existing:
            return existing[0]

        rule = next(filter(lambda action: action.role == role, self.rule.actions), None)
        if not rule:
            raise ValueError(f"Rule for {role} not found in construct {self.rule.name}")

        action = Action(
            ast_id=self.ast_id,
            values=[],
            rule=rule,
            parent=self,
            owner=self.owner,
        )
        self.owner.add(action)
        return action


@dataclass(slots=True)
class TraceAct:
    action: Action
    used_transition: TransitionDeclaration | None
    situation: SituationContext

    @property
    def chain(self) -> list[TraceAct]:
        return self.situation.trace_acts

    @property
    def chain_order(self) -> int:
        return _chain_order(self.chain, self)


@dataclass(slots=True)
class TraceState:
    interruption_mode: InterruptionType


def _chain_order[T](chain: list[T], item: T) -> int:
    return chain.index(item) if item in chain else len(chain)
