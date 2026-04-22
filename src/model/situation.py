from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.ast_managers import CodeManager
from src.model.rules import ActionDeclaration, ConstructDeclaration, TransitionDeclaration


class SituationContext(Protocol):
    def code(self) -> CodeManager:
        ...

    def get_construct_for(self, ast_id: int) -> Construct:
        ...

    def get_actions_for(self, ast_id: int) -> list[Action]:
        ...

    def get_related_actions(self, construct: Construct) -> list[Action]:
        ...

    def add(self, object: Any):
        pass


class OrderedChain[T](Protocol):
    @property
    def chain(self) -> list[T]:
        ...

    @property
    def chain_order(self) -> int:
        ...


@dataclass(slots=True)
class Action:
    ast_id: int
    ast_jump_id: int | None
    values: list[bool]
    rule: ActionDeclaration
    parent: Construct
    owner: SituationContext

    @property
    def chain(self) -> list[Action]:
        pass

    def possible_transitions(self) -> list[TransitionDeclaration]:
        pass

    @property
    def chain_order(self) -> int:
        pass

    def is_atomic(self) -> bool:
        pass

    def expands_to(self) -> Construct | None:
        pass


@dataclass(slots=True)
class Construct:
    parent: Construct
    ast_id: int
    rule: ConstructDeclaration
    owner: SituationContext

    def __post_init__(self):
        self.begin_action()
        self.end_action()

    @property
    def actions(self):
        pass

    def action_by_role(self, role: str) -> list[Action]:
        pass

    def begin_action(self) -> Action:
        pass

    def end_action(self) -> Action:
        pass


@dataclass(slots=True)
class TraceAct:
    action: Action
    used_transition: TransitionDeclaration | None
    situation: SituationContext

    @property
    def chain(self) -> list[TraceAct]:
        pass

    @property
    def chain_order(self) -> int:
        pass