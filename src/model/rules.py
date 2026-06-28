from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import yaml

from src.json_property_path import ResolvedJSONPath, resolve_json_property_path
from src.json_search import JSONPath, get_node_by_path
from src.model.ast_node_query import AstNodeQuery, AstNodeQuerySource
from src.types import JSON, Node

type AstNodeTypeMatcher = Callable[[Node, str], bool]

_BOUNDARY_ACTION_ROLES = {"BEGIN", "END"}


class InterruptionType(StrEnum):
    BREAK = "break"
    CONTINUE = "continue"
    RETURN = "return"
    EXCEPTION = "exception"
    ANY = "any"
    NONE = "none"


class CallStackAction(StrEnum):
    NONE = "none"
    ADD_FRAME = "add_frame"
    DROP_FRAME = "drop_frame"


@dataclass(slots=True)
class Metadata:
    locale_trace_name: str | None = None
    locale_pronoun: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def flag(self, name, value: bool | None = None) -> bool | None:
        if value:
            self.extra[name] = value
        return cast(bool, self.extra.get(name))

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Metadata | None:
        if data is None:
            return None
        known_keys = {"locale_trace_name", "locale_pronoun"}
        extra = {key: value for key, value in data.items() if key not in known_keys}
        return cls(
            locale_trace_name=data.get("locale_trace_name"),
            locale_pronoun=data.get("locale_pronoun"),
            extra=extra,
        )


@dataclass(slots=True)
class Identification:
    origin: str | None = None
    property: str | None = None
    property_path: str | None = None
    role_in_list: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Identification | None:
        if data is None:
            return None
        return cls(
            origin=data.get("origin"),
            property=data.get("property"),
            property_path=data.get("property_path"),
            role_in_list=data.get("role_in_list"),
        )

    def resolve_json(
        self,
        data: JSON,
        *,
        current_path: JSONPath = (),
        previous_path: JSONPath | None = None,
    ) -> ResolvedJSONPath | None:
        if self.property_path:
            return _resolve_property_path_identification(
                data,
                self.property_path,
                origin=self.origin,
                current_path=current_path,
                previous_path=previous_path,
            )

        if self.role_in_list:
            return _resolve_role_in_list_identification(
                data,
                role_in_list=self.role_in_list,
                property_name=self.property,
                origin=self.origin,
                current_path=current_path,
                previous_path=previous_path,
            )

        base_path = _resolve_property_base_path(
            self.origin,
            current_path=current_path,
            previous_path=previous_path,
        )
        if base_path is None:
            return None

        if self.property:
            resolved_path = (*base_path, self.property)
            missing = object()
            value = get_node_by_path(data, resolved_path, default=missing)
            if value is missing:
                return None
            return ResolvedJSONPath(path=resolved_path, value=value)

        missing = object()
        value = get_node_by_path(data, base_path, default=missing)
        if value is missing:
            return None
        return ResolvedJSONPath(path=base_path, value=value)

    def get_from_json(
        self,
        data: JSON,
        *,
        current_path: JSONPath = (),
        previous_path: JSONPath | None = None,
        default: Any = None,
    ) -> Any:
        resolved = self.resolve_json(
            data,
            current_path=current_path,
            previous_path=previous_path,
        )
        if resolved is None:
            return default
        return resolved.value


@dataclass(slots=True)
class Behaviour:
    assumed_value: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Behaviour | None:
        if data is None:
            return None
        return cls(assumed_value=data.get("assumed_value"))


@dataclass(slots=True)
class EffectDeclaration:
    interruption_start: InterruptionType | None = None
    interruption_stop: InterruptionType | None = None
    call_stack: CallStackAction | None = None

    def __post_init__(self) -> None:
        self.interruption_start = _coerce_interruption_type(self.interruption_start)
        self.interruption_stop = _coerce_interruption_type(self.interruption_stop)
        self.call_stack = _coerce_call_stack_action(self.call_stack)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EffectDeclaration:
        return cls(
            interruption_start=_coerce_interruption_type(
                data.get("interruption_start")
            ),
            interruption_stop=_coerce_interruption_type(data.get("interruption_stop")),
            call_stack=_coerce_call_stack_action(data.get("call_stack")),
        )


@dataclass(slots=True)
class ConstraintsDeclaration:
    condition_value: bool | None = None
    interruption_mode: InterruptionType | None = None

    def __post_init__(self) -> None:
        self.interruption_mode = _coerce_interruption_type(self.interruption_mode)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ConstraintsDeclaration | None:
        if data is None:
            return None
        return cls(
            condition_value=data.get("condition_value"),
            interruption_mode=_coerce_interruption_type(data.get("interruption_mode")),
        )


@dataclass(slots=True)
class ActionDeclaration:
    role: str
    kind: str
    opaque: bool | None = None
    identification: Identification | None = None
    metadata: Metadata | None = None
    generalization: str | None = None
    behaviour: Behaviour | None = None
    effects: EffectDeclaration | None = None
    parent: ConstructDeclaration | None = field(
        default=None, init=False, repr=False, compare=False
    )

    @property
    def is_opaque(self) -> bool:
        if self.opaque is not None:
            return self.opaque
        return _default_action_opaque(self.role)

    @property
    def kind_classes(self) -> set[str]:
        return set(self.kind.split("."))

    @property
    def is_optional(self) -> bool:
        return "optional" in self.kind_classes

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionDeclaration:
        return cls(
            role=data["role"],
            kind=data["kind"],
            opaque=data.get("opaque"),
            identification=Identification.from_dict(data.get("identification")),
            metadata=Metadata.from_dict(data.get("metadata")),
            generalization=data.get("generalization"),
            behaviour=Behaviour.from_dict(data.get("behaviour")),
            effects=_load_effect(data.get("effects")),
        )


@dataclass(slots=True)
class TransitionDeclaration:
    from_role: str
    to_role: str
    to_when_absent: str | list[str] | None = None
    constraints: ConstraintsDeclaration | None = None
    effects: EffectDeclaration | None = None
    parent: ConstructDeclaration | None = field(
        default=None, init=False, repr=False, compare=False
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransitionDeclaration:
        return cls(
            from_role=data["from"],
            to_role=data["to"],
            to_when_absent=data.get("to_when_absent"),
            constraints=ConstraintsDeclaration.from_dict(data.get("constraints")),
            effects=_load_effect(data.get("effects")),
        )


@dataclass(slots=True)
class ConstructDeclaration:
    name: str
    kind: str
    ast_node: AstNodeQuerySource
    applicable_languages: list[str] = field(default_factory=list)
    metadata: Metadata | None = None
    effects: EffectDeclaration | None = None
    actions: list[ActionDeclaration] = field(default_factory=list)
    transitions: list[TransitionDeclaration] = field(default_factory=list)

    @property
    def kind_classes(self) -> set[str]:
        return set(self.kind.split("."))

    @property
    def has_runtime_actions(self) -> bool:
        return any(action.role not in {"BEGIN", "END"} for action in self.actions)

    @property
    def is_atomic_inline(self) -> bool:
        return "inline" in self.kind_classes and not self.has_runtime_actions

    @property
    def should_build_construct(self) -> bool:
        return "external" in self.kind_classes or (
            "noop" not in self.kind_classes and not self.is_atomic_inline
        )

    def __post_init__(self) -> None:
        self.ast_node = AstNodeQuery.from_raw(self.ast_node)
        self.actions = _ensure_boundary_actions(self.actions)
        for action in self.actions:
            if action.parent is not None:
                raise ValueError(
                    f"Action {action.role!r} in construct {self.name!r} has multiple parents: {action.parent.name!r} and {self.name!r}"
                )
            action.parent = self
        for transition in self.transitions:
            if transition.parent is not None:
                raise ValueError(
                    f"Transition {transition.from_role!r}->{transition.to_role!r} in construct {self.name!r} has multiple parents: {transition.parent.name!r} and {self.name!r}"
                )
            transition.parent = self

    def applicable_to_language(self, language: str) -> bool:
        return not self.applicable_languages or language in self.applicable_languages

    def matches_ast_node(
        self,
        node: Node,
        type_matcher: AstNodeTypeMatcher | None = None,
    ) -> bool:
        return self.ast_node_query.matches(node, type_matcher=type_matcher)

    @property
    def ast_node_query(self) -> AstNodeQuery:
        return cast(AstNodeQuery, self.ast_node)

    def compiled_transitions(self) -> list[TransitionDeclaration]:
        result: list[TransitionDeclaration] = []
        actions_by_generalization = self._actions_by_generalization()
        effects_by_role = {
            action.role: action.effects
            for action in self.actions
            if action.effects is not None
        }

        for transition in self.transitions:
            expanded_from_roles = actions_by_generalization.get(transition.from_role)
            from_roles = (
                expanded_from_roles
                if expanded_from_roles is not None
                else [transition.from_role]
            )
            for from_role in from_roles:
                compiled = _copy_transition(transition, from_role=from_role)
                compiled.effects = _merge_effects(
                    compiled.effects, effects_by_role.get(from_role)
                )
                if compiled.to_role == "END":
                    compiled.effects = _merge_effects(compiled.effects, self.effects)
                result.append(compiled)
        return _add_optional_absent_targets(result, self.actions)

    def compiled_transitions_from_role(self, role: str) -> list[TransitionDeclaration]:
        action = self.action_declaration_by_role(role)
        roles = {role}
        if action is None:
            roles.update(
                action.role for action in self.actions if action.generalization == role
            )
        return [
            transition
            for transition in self.compiled_transitions()
            if transition.from_role in roles
        ]

    def compiled_transitions_for_action(
        self, action: ActionDeclaration
    ) -> list[TransitionDeclaration]:
        return [
            transition
            for transition in self.compiled_transitions()
            if transition.from_role == action.role
        ]

    def action_declaration_by_role(self, role: str) -> ActionDeclaration | None:
        return next((action for action in self.actions if action.role == role), None)

    def _actions_by_generalization(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for action in self.actions:
            if action.generalization is None:
                continue
            result.setdefault(action.generalization, []).append(action.role)
        return result

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> ConstructDeclaration:
        return cls(
            name=name,
            kind=data["kind"],
            ast_node=data["ast_node"],
            applicable_languages=list(data.get("applicable_languages", [])),
            metadata=Metadata.from_dict(data.get("metadata")),
            effects=_load_effect(data.get("effects")),
            actions=[
                ActionDeclaration.from_dict(item) for item in data.get("actions", [])
            ],
            transitions=[
                TransitionDeclaration.from_dict(item)
                for item in data.get("transitions", [])
            ],
        )


def load_construct_declarations(path: str | Path) -> list[ConstructDeclaration]:
    with Path(path).open(encoding="utf-8") as file:
        raw_data = yaml.safe_load(file) or {}
    return load_construct_declarations_from_dict(raw_data)


def load_construct_declarations_from_dict(
    data: dict[str, Any],
) -> list[ConstructDeclaration]:
    declarations: list[ConstructDeclaration] = []
    for name, rule_data in data.items():
        if not _is_construct_rule_data(name, rule_data):
            continue
        if rule_data.get("disabled", False):
            continue
        declarations.append(ConstructDeclaration.from_dict(name, rule_data))
    _ensure_unique_ast_node_queries(declarations)
    return declarations


def locate_construct_declaration_by_ast_node(
    ast_data: str | Node,
    declarations: list[ConstructDeclaration],
    safe_mode: bool = True,
    type_matcher: AstNodeTypeMatcher | None = None,
) -> ConstructDeclaration | None:
    node: Node = {"type": ast_data} if isinstance(ast_data, str) else ast_data
    matches: list[ConstructDeclaration] = []
    for declaration in declarations:
        if declaration.matches_ast_node(node, type_matcher=type_matcher):
            matches.append(declaration)
        if matches and not safe_mode:
            break
    if not matches:
        return None

    best_specificity = max(match.ast_node_query.specificity() for match in matches)
    best_matches = [
        match
        for match in matches
        if match.ast_node_query.specificity() == best_specificity
    ]
    if len(best_matches) == 1:
        return best_matches[0]

    matched_names = ", ".join(repr(match.name) for match in best_matches)
    raise ValueError(
        f"Multiple equally specific construct declarations match AST node type {ast_data!r}: {matched_names}"
    )


def _is_construct_rule_data(name: str, data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    has_kind = "kind" in data
    has_ast_node = "ast_node" in data
    if has_kind and has_ast_node:
        return True
    if not has_kind and not has_ast_node:
        return False
    missing_key = "kind" if not has_kind else "ast_node"
    raise ValueError(f"Construct declaration {name!r} must contain {missing_key!r}")


def _load_effect(
    data: dict[str, Any] | list[dict[str, Any]] | None,
) -> EffectDeclaration | None:
    if not data:
        return None
    if isinstance(data, dict):
        return EffectDeclaration.from_dict(data)

    merged: dict[str, Any] = {}
    for item in data:
        for key, value in item.items():
            if key in merged and merged[key] != value:
                raise ValueError(
                    f"Conflicting effect value for {key!r}: {merged[key]!r} != {value!r}"
                )
            merged[key] = value
    return EffectDeclaration.from_dict(merged)


def _ensure_boundary_actions(
    actions: list[ActionDeclaration],
) -> list[ActionDeclaration]:
    existing_roles = {action.role for action in actions}
    result: list[ActionDeclaration] = []
    if "BEGIN" not in existing_roles:
        result.append(ActionDeclaration(role="BEGIN", kind="BEGIN"))
    result.extend(actions)
    if "END" not in existing_roles:
        result.append(ActionDeclaration(role="END", kind="END"))
    return result


def _default_action_opaque(role: str) -> bool:
    return role not in _BOUNDARY_ACTION_ROLES


def _copy_transition(
    transition: TransitionDeclaration, *, from_role: str
) -> TransitionDeclaration:
    to_when_absent = (
        transition.to_when_absent.copy()
        if isinstance(transition.to_when_absent, list)
        else transition.to_when_absent
    )
    result = TransitionDeclaration(
        from_role=from_role,
        to_role=transition.to_role,
        to_when_absent=to_when_absent,
        constraints=transition.constraints,
        effects=_copy_effect(transition.effects),
    )
    result.parent = transition.parent
    return result


def _add_optional_absent_targets(
    transitions: list[TransitionDeclaration],
    actions: list[ActionDeclaration],
) -> list[TransitionDeclaration]:
    optional_roles = {action.role for action in actions if action.is_optional}
    if not optional_roles:
        return transitions

    targets_by_optional_role: dict[str, list[str]] = {}
    for transition in transitions:
        if transition.from_role not in optional_roles:
            continue
        targets_by_optional_role.setdefault(transition.from_role, []).append(
            transition.to_role
        )

    for transition in transitions:
        if transition.to_when_absent is not None:
            continue
        if transition.to_role not in optional_roles:
            continue
        skip_targets = targets_by_optional_role.get(transition.to_role, [])
        if not skip_targets:
            continue
        transition.to_when_absent = (
            skip_targets[0] if len(skip_targets) == 1 else skip_targets.copy()
        )
    return transitions


def _copy_effect(effect: EffectDeclaration | None) -> EffectDeclaration | None:
    if effect is None:
        return None
    return EffectDeclaration(
        interruption_start=effect.interruption_start,
        interruption_stop=effect.interruption_stop,
        call_stack=effect.call_stack,
    )


def _merge_effects(
    base: EffectDeclaration | None, added: EffectDeclaration | None
) -> EffectDeclaration | None:
    if added is None:
        return base
    if base is None:
        return _copy_effect(added)
    return EffectDeclaration(
        interruption_start=base.interruption_start
        if base.interruption_start is not None
        else added.interruption_start,
        interruption_stop=base.interruption_stop
        if base.interruption_stop is not None
        else added.interruption_stop,
        call_stack=base.call_stack if base.call_stack is not None else added.call_stack,
    )


def _ensure_unique_ast_node_queries(declarations: list[ConstructDeclaration]) -> None:
    seen: dict[tuple[Any, ...], str] = {}
    for declaration in declarations:
        for key in declaration.ast_node_query.duplicate_keys():
            previous = seen.get(key)
            if previous is not None:
                raise ValueError(
                    f"Duplicate ast_node predicate {key!r} in constructs {previous!r} and {declaration.name!r}"
                )
            seen[key] = declaration.name


def _resolve_property_path_identification(
    data: JSON,
    property_path: str,
    *,
    origin: str | None,
    current_path: JSONPath,
    previous_path: JSONPath | None,
) -> ResolvedJSONPath | None:
    if origin == "previous":
        return resolve_json_property_path(
            data,
            property_path,
            previous_path=previous_path,
            origin="previous",
        )
    return resolve_json_property_path(
        data,
        property_path,
        current_path=current_path,
    )


def _resolve_role_in_list_identification(
    data: JSON,
    *,
    role_in_list: str,
    property_name: str | None,
    origin: str | None,
    current_path: JSONPath,
    previous_path: JSONPath | None,
) -> ResolvedJSONPath | None:
    container_path = _resolve_property_base_path(
        origin,
        current_path=current_path,
        previous_path=previous_path,
    )
    if container_path is None:
        return None

    if property_name:
        container_path = (*container_path, property_name)

    missing = object()
    container = get_node_by_path(data, container_path, default=missing)
    if container is missing or not isinstance(container, list):
        return None

    if role_in_list == "first_in_list":
        if not container:
            return None
        resolved_path = (*container_path, 0)
        return ResolvedJSONPath(path=resolved_path, value=container[0])

    if role_in_list == "next_in_list":
        if previous_path is None:
            return None
        next_index = _resolve_next_list_index(container_path, previous_path)
        if next_index is None or next_index >= len(container):
            return None
        resolved_path = (*container_path, next_index)
        return ResolvedJSONPath(path=resolved_path, value=container[next_index])

    return None


def _resolve_property_base_path(
    origin: str | None,
    *,
    current_path: JSONPath,
    previous_path: JSONPath | None,
) -> JSONPath | None:
    if origin == "previous":
        return previous_path
    if origin == "parent":
        if not current_path:
            return None
        return current_path[:-1]
    return current_path


def _resolve_next_list_index(
    container_path: JSONPath, previous_path: JSONPath
) -> int | None:
    if (
        len(previous_path) == len(container_path) + 1
        and previous_path[: len(container_path)] == container_path
    ):
        last_step = previous_path[-1]
        if isinstance(last_step, int):
            return last_step + 1
    return None


def _coerce_interruption_type(
    value: InterruptionType | str | None,
) -> InterruptionType | None:
    if value is None or isinstance(value, InterruptionType):
        return value
    return InterruptionType(value)


def _coerce_call_stack_action(
    value: CallStackAction | str | None,
) -> CallStackAction | None:
    if value is None or isinstance(value, CallStackAction):
        return value
    return CallStackAction(value)
