from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.model.rules import ActionDeclaration, ConstructDeclaration, TransitionDeclaration


class ConstructAutomatonValidationError(ValueError):
    pass


class AmbiguousTransitionError(ConstructAutomatonValidationError):
    pass


@dataclass(frozen=True, slots=True)
class LoopInfo:
    index: int
    roles: frozenset[str]
    entry_roles: frozenset[str]
    exit_roles: frozenset[str]

    def contains(self, role: str) -> bool:
        return role in self.roles


@dataclass(frozen=True, slots=True)
class ConstructAutomatonStep:
    action: ActionDeclaration
    incoming_transition: TransitionDeclaration | None
    outgoing_transitions: tuple[TransitionDeclaration, ...]
    loop: LoopInfo | None = None
    starts_loop_iteration: bool = False
    ends_loop_iteration: bool = False

    @property
    def role(self) -> str:
        return self.action.role


@dataclass(frozen=True, slots=True)
class LoopControl:
    loop: LoopInfo
    action: ActionDeclaration
    inside_transitions: tuple[TransitionDeclaration, ...]
    exit_transitions: tuple[TransitionDeclaration, ...]

    @property
    def role(self) -> str:
        return self.action.role

    @property
    def condition_values(self) -> tuple[bool, ...]:
        values: list[bool] = []
        for transition in (*self.inside_transitions, *self.exit_transitions):
            constraints = transition.constraints
            if constraints is None or constraints.condition_value is None:
                continue
            values.append(constraints.condition_value)
        return tuple(values)


@dataclass(frozen=True, slots=True)
class SelfLoopControl:
    loop: LoopInfo
    action: ActionDeclaration
    transition: TransitionDeclaration
    absent_roles: tuple[str, ...]

    @property
    def role(self) -> str:
        return self.action.role


class ConstructTransitionAutomaton:
    def __init__(self, construct: ConstructDeclaration) -> None:
        self.construct = construct
        self.actions_by_role = {action.role: action for action in construct.actions}
        self.transitions = tuple(construct.compiled_transitions())
        self._transitions_by_from = _group_transitions_by_from(self.transitions)
        self._edges_by_from = _group_edges_by_from(self.transitions)
        self._loops = _find_loops(self._edges_by_from)
        self._loops_by_role = {
            role: loop
            for loop in self._loops
            for role in loop.roles
        }
        self.validate()

    @property
    def loops(self) -> tuple[LoopInfo, ...]:
        return self._loops

    @property
    def repeated_value_roles(self) -> frozenset[str]:
        return frozenset(control.role for control in self.loop_controls())

    @property
    def repeated_action_roles(self) -> frozenset[str]:
        return frozenset(control.role for control in self.self_loop_controls())

    def action_by_role(self, role: str) -> ActionDeclaration:
        try:
            return self.actions_by_role[role]
        except KeyError as error:
            raise ConstructAutomatonValidationError(
                f"Construct {self.construct.name!r} references unknown action role {role!r}"
            ) from error

    def transitions_from(self, role: str) -> tuple[TransitionDeclaration, ...]:
        return self._transitions_by_from.get(role, ())

    def loop_controls(self) -> tuple[LoopControl, ...]:
        controls: list[LoopControl] = []
        for loop in self.loops:
            for role in sorted(loop.entry_roles):
                action = self.action_by_role(role)
                inside_transitions: list[TransitionDeclaration] = []
                exit_transitions: list[TransitionDeclaration] = []

                for transition in self.transitions_from(role):
                    if not _uses_condition_value(transition):
                        continue
                    targets = (transition.to_role, *_absent_roles(transition))
                    if any(target in loop.roles for target in targets):
                        inside_transitions.append(transition)
                    if any(target not in loop.roles for target in targets):
                        exit_transitions.append(transition)

                if inside_transitions and exit_transitions:
                    controls.append(
                        LoopControl(
                            loop=loop,
                            action=action,
                            inside_transitions=tuple(inside_transitions),
                            exit_transitions=tuple(exit_transitions),
                        )
                    )
        return tuple(controls)

    def controls_loop(self, action: ActionDeclaration) -> bool:
        return action.role in self.repeated_value_roles

    def self_loop_controls(self) -> tuple[SelfLoopControl, ...]:
        controls: list[SelfLoopControl] = []
        for loop in self.loops:
            if len(loop.roles) != 1:
                continue
            role = next(iter(loop.roles))
            action = self.action_by_role(role)

            for transition in self.transitions_from(role):
                absent_roles = _absent_roles(transition)
                if transition.to_role != role:
                    continue
                if not absent_roles:
                    continue
                if not any(absent_role not in loop.roles for absent_role in absent_roles):
                    continue
                controls.append(
                    SelfLoopControl(
                        loop=loop,
                        action=action,
                        transition=transition,
                        absent_roles=absent_roles,
                    )
                )
        return tuple(controls)

    def repeats_action(self, action: ActionDeclaration) -> bool:
        return action.role in self.repeated_action_roles

    def initial_step(self, role: str = "BEGIN") -> ConstructAutomatonStep:
        return self._build_step(role, incoming_transition=None, previous_role=None)

    def first_step(self) -> ConstructAutomatonStep:
        begin = self.initial_step()
        transition = self._single_transition(begin)
        return self.step(begin, transition)

    def next_step(
        self,
        current: ConstructAutomatonStep,
        transition: TransitionDeclaration | None = None,
        *,
        absent: bool = False,
        absent_index: int = 0,
    ) -> ConstructAutomatonStep | None:
        if transition is None:
            if not current.outgoing_transitions:
                return None
            transition = self._single_transition(current)
        return self.step(current, transition, absent=absent, absent_index=absent_index)

    def step(
        self,
        current: ConstructAutomatonStep | str,
        transition: TransitionDeclaration,
        *,
        absent: bool = False,
        absent_index: int = 0,
    ) -> ConstructAutomatonStep:
        current_role = current if isinstance(current, str) else current.role
        if transition.from_role != current_role:
            raise ConstructAutomatonValidationError(
                f"Transition from {transition.from_role!r} cannot be applied to current role {current_role!r}"
            )
        next_role = _transition_target(transition, absent=absent, absent_index=absent_index)
        return self._build_step(next_role, incoming_transition=transition, previous_role=current_role)

    def iter_steps(
        self,
        *,
        include_begin: bool = False,
        max_steps: int = 1000,
    ) -> Iterable[ConstructAutomatonStep]:
        current = self.initial_step()
        if include_begin:
            yield current
        current = self.next_step(current)

        steps_count = 0
        while current is not None:
            yield current
            steps_count += 1
            if steps_count >= max_steps:
                raise ConstructAutomatonValidationError(
                    f"Automaton path for construct {self.construct.name!r} exceeded {max_steps} steps"
                )
            current = self.next_step(current)

    def iter_path(
        self,
        *,
        include_begin: bool = True,
        max_steps: int = 1000,
    ) -> Iterable[ConstructAutomatonStep]:
        return self.iter_steps(include_begin=include_begin, max_steps=max_steps)

    def validate(self) -> None:
        begin_transitions = self.transitions_from("BEGIN")
        if len(begin_transitions) > 1:
            raise ConstructAutomatonValidationError(
                f"Construct {self.construct.name!r} must have exactly one (or zero) transition from BEGIN"
            )

        unknown_roles = sorted(self._referenced_roles() - self.actions_by_role.keys())
        if unknown_roles:
            raise ConstructAutomatonValidationError(
                f"Construct {self.construct.name!r} references unknown action roles: {', '.join(unknown_roles)}"
            )

        infinite_loops = [loop for loop in self._loops if not loop.exit_roles]
        if infinite_loops:
            loop_roles = ", ".join(
                "{" + ", ".join(sorted(loop.roles)) + "}"
                for loop in infinite_loops
            )
            raise ConstructAutomatonValidationError(
                f"Construct {self.construct.name!r} has non-terminating transition loops: {loop_roles}"
            )

    def to_dot(self) -> str:
        lines = [
            f"digraph {_dot_id(self.construct.name)} {{",
            "    rankdir=LR;",
        ]

        for action in self.construct.actions:
            attributes = {
                "label": action.role,
                "shape": "box",
            }
            loop = self._loops_by_role.get(action.role)
            if loop is not None:
                attributes.update({"style": "filled", "fillcolor": "lightyellow"})
                if action.role in loop.entry_roles:
                    attributes.update({"color": "orange", "penwidth": "2"})
            lines.append(f"    {_dot_node_ref(action.role)} [{_dot_attributes(attributes)}];")

        for transition in self.transitions:
            edges = [(transition.to_role, False)]
            edges.extend((role, True) for role in _absent_roles(transition))
            for target, is_absent in edges:
                attributes: dict[str, str] = {}
                if is_absent:
                    attributes.update({"style": "dashed", "label": "absent"})
                attr_text = f" [{_dot_attributes(attributes)}]" if attributes else ""
                lines.append(f"    {_dot_node_ref(transition.from_role)} -> {_dot_node_ref(target)}{attr_text};")

        lines.append("}")
        return "\n".join(lines)

    def write_png(self, path: str | Path) -> None:
        import pydot

        graphs = pydot.graph_from_dot_data(self.to_dot())
        if not graphs:
            raise ConstructAutomatonValidationError(
                f"Could not render DOT for construct automaton {self.construct.name!r}"
            )
        graphs[0].write_png(str(path)) # type: ignore

    def _build_step(
        self,
        role: str,
        *,
        incoming_transition: TransitionDeclaration | None,
        previous_role: str | None,
    ) -> ConstructAutomatonStep:
        action = self.action_by_role(role)
        loop = self._loops_by_role.get(role)
        starts_loop_iteration = False
        ends_loop_iteration = False

        if loop is not None and role in loop.entry_roles:
            starts_loop_iteration = True
            ends_loop_iteration = previous_role in loop.roles if previous_role is not None else False

        return ConstructAutomatonStep(
            action=action,
            incoming_transition=incoming_transition,
            outgoing_transitions=self.transitions_from(role),
            loop=loop,
            starts_loop_iteration=starts_loop_iteration,
            ends_loop_iteration=ends_loop_iteration,
        )

    def _single_transition(self, step: ConstructAutomatonStep) -> TransitionDeclaration:
        if len(step.outgoing_transitions) != 1:
            raise AmbiguousTransitionError(
                f"Action {step.role!r} in construct {self.construct.name!r} has "
                f"{len(step.outgoing_transitions)} outgoing transitions; choose one explicitly"
            )
        return step.outgoing_transitions[0]

    def _referenced_roles(self) -> set[str]:
        result: set[str] = set()
        for transition in self.transitions:
            result.add(transition.from_role)
            result.add(transition.to_role)
            result.update(_absent_roles(transition))
        return result


def _group_transitions_by_from(
    transitions: Iterable[TransitionDeclaration],
) -> dict[str, tuple[TransitionDeclaration, ...]]:
    grouped: dict[str, list[TransitionDeclaration]] = {}
    for transition in transitions:
        grouped.setdefault(transition.from_role, []).append(transition)
    return {role: tuple(items) for role, items in grouped.items()}


def _group_edges_by_from(transitions: Iterable[TransitionDeclaration]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for transition in transitions:
        grouped.setdefault(transition.from_role, set()).add(transition.to_role)
        grouped[transition.from_role].update(_absent_roles(transition))
    return grouped


def _find_loops(edges_by_from: dict[str, set[str]]) -> tuple[LoopInfo, ...]:
    components = _strongly_connected_components(edges_by_from)
    loops: list[LoopInfo] = []
    for component in components:
        if len(component) == 1:
            role = next(iter(component))
            if role not in edges_by_from.get(role, set()):
                continue

        entry_roles = _entry_roles(component, edges_by_from)
        exit_roles = _exit_roles(component, edges_by_from)
        loops.append(
            LoopInfo(
                index=len(loops),
                roles=frozenset(component),
                entry_roles=frozenset(entry_roles or component),
                exit_roles=frozenset(exit_roles),
            )
        )
    return tuple(loops)


def _strongly_connected_components(edges_by_from: dict[str, set[str]]) -> list[set[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[set[str]] = []

    def strongconnect(role: str) -> None:
        nonlocal index
        indices[role] = index
        lowlinks[role] = index
        index += 1
        stack.append(role)
        on_stack.add(role)

        for target in edges_by_from.get(role, set()):
            if target not in indices:
                strongconnect(target)
                lowlinks[role] = min(lowlinks[role], lowlinks[target])
            elif target in on_stack:
                lowlinks[role] = min(lowlinks[role], indices[target])

        if lowlinks[role] != indices[role]:
            return

        component: set[str] = set()
        while True:
            target = stack.pop()
            on_stack.remove(target)
            component.add(target)
            if target == role:
                break
        components.append(component)

    roles = set(edges_by_from)
    for targets in edges_by_from.values():
        roles.update(targets)

    for role in roles:
        if role not in indices:
            strongconnect(role)

    return components


def _entry_roles(component: set[str], edges_by_from: dict[str, set[str]]) -> set[str]:
    entries: set[str] = set()
    for source, targets in edges_by_from.items():
        if source in component:
            continue
        entries.update(target for target in targets if target in component)
    return entries


def _exit_roles(component: set[str], edges_by_from: dict[str, set[str]]) -> set[str]:
    exits: set[str] = set()
    for source in component:
        exits.update(target for target in edges_by_from.get(source, set()) if target not in component)
    return exits


def _transition_target(
    transition: TransitionDeclaration,
    *,
    absent: bool,
    absent_index: int,
) -> str:
    if not absent:
        return transition.to_role
    absent_roles = _absent_roles(transition)
    try:
        return absent_roles[absent_index]
    except IndexError as error:
        raise ConstructAutomatonValidationError(
            f"Transition from {transition.from_role!r} to {transition.to_role!r} has no absent target at index {absent_index}"
        ) from error


def _absent_roles(transition: TransitionDeclaration) -> tuple[str, ...]:
    if transition.to_when_absent is None:
        return ()
    if isinstance(transition.to_when_absent, list):
        return tuple(transition.to_when_absent)
    return (transition.to_when_absent,)


def _uses_condition_value(transition: TransitionDeclaration) -> bool:
    return transition.constraints is not None and transition.constraints.condition_value is not None


def _dot_id(value: str) -> str:
    normalized = "".join(char if char.isalnum() or char == "_" else "_" for char in value)
    if not normalized:
        return "automaton"
    if normalized[0].isdigit():
        return f"automaton_{normalized}"
    return normalized


def _dot_node_ref(value: Any) -> str:
    return f'"{_dot_escape(str(value))}"'


def _dot_attributes(attributes: dict[str, str]) -> str:
    return ", ".join(f'{name}="{_dot_escape(value)}"' for name, value in attributes.items())


def _dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
