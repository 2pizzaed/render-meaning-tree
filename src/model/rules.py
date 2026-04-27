from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import yaml

from src.json_property_path import ResolvedJSONPath, resolve_json_property_path
from src.json_search import JSONPath, get_node_by_path
from src.model.ast_node_query import AstNodeQuery, AstNodeQuerySource
from src.types import JSON, Node


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
            interruption_start=_coerce_interruption_type(data.get("interruption_start")),
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
    identification: Identification | None = None
    metadata: Metadata | None = None
    generalization: str | None = None
    behaviour: Behaviour | None = None
    effects: EffectDeclaration | None = None
    parent: ConstructDeclaration | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def kind_classes(self) -> set[str]:
        return set(self.kind.split("."))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionDeclaration:
        return cls(
            role=data["role"],
            kind=data["kind"],
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

    def __post_init__(self) -> None:
        self.ast_node = AstNodeQuery.from_raw(self.ast_node)
        for action in self.actions:
            if action.parent is not None:
                raise ValueError(f"Action {action.role!r} in construct {self.name!r} has multiple parents: {action.parent.name!r} and {self.name!r}")
            action.parent = self

    def applicable_to_language(self, language: str) -> bool:
        return not self.applicable_languages or language in self.applicable_languages

    def matches_ast_node(self, node: Node) -> bool:
        return self.ast_node_query.matches(node)

    @property
    def ast_node_query(self) -> AstNodeQuery:
        return cast(AstNodeQuery, self.ast_node)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> ConstructDeclaration:
        return cls(
            name=name,
            kind=data["kind"],
            ast_node=data["ast_node"],
            applicable_languages=list(data.get("applicable_languages", [])),
            metadata=Metadata.from_dict(data.get("metadata")),
            effects=_load_effect(data.get("effects")),
            actions=[ActionDeclaration.from_dict(item) for item in data.get("actions", [])],
            transitions=[TransitionDeclaration.from_dict(item) for item in data.get("transitions", [])],
        )


def load_construct_declarations(path: str | Path) -> list[ConstructDeclaration]:
    with Path(path).open(encoding="utf-8") as file:
        raw_data = yaml.safe_load(file) or {}
    return load_construct_declarations_from_dict(raw_data)


def load_construct_declarations_from_dict(data: dict[str, Any]) -> list[ConstructDeclaration]:
    declarations: list[ConstructDeclaration] = []
    for name, rule_data in data.items():
        if rule_data.get("disabled", False):
            continue
        declarations.append(ConstructDeclaration.from_dict(name, rule_data))
    _ensure_unique_ast_node_queries(declarations)
    return declarations


def locate_construct_declaration_by_ast_node(
    ast_data: str | Node, declarations: list[ConstructDeclaration], safe_mode: bool = True
) -> ConstructDeclaration | None:
    node: Node = {"type": ast_data} if isinstance(ast_data, str) else ast_data
    result: ConstructDeclaration | None = None
    for declaration in declarations:
        if declaration.matches_ast_node(node):
            if result is not None:
                raise ValueError(f"Multiple construct declarations match AST node type {ast_data!r}: {result.name!r} and {declaration.name!r}")
            result = declaration
        if result is not None and not safe_mode:
            break
    return result


def _load_effect(data: dict[str, Any] | list[dict[str, Any]] | None) -> EffectDeclaration | None:
    if not data:
        return None
    if isinstance(data, dict):
        return EffectDeclaration.from_dict(data)

    merged: dict[str, Any] = {}
    for item in data:
        for key, value in item.items():
            if key in merged and merged[key] != value:
                raise ValueError(f"Conflicting effect value for {key!r}: {merged[key]!r} != {value!r}")
            merged[key] = value
    return EffectDeclaration.from_dict(merged)


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


def _resolve_next_list_index(container_path: JSONPath, previous_path: JSONPath) -> int | None:
    if len(previous_path) == len(container_path) + 1 and previous_path[: len(container_path)] == container_path:
        last_step = previous_path[-1]
        if isinstance(last_step, int):
            return last_step + 1
    return None


def _coerce_interruption_type(value: InterruptionType | str | None) -> InterruptionType | None:
    if value is None or isinstance(value, InterruptionType):
        return value
    return InterruptionType(value)


def _coerce_call_stack_action(value: CallStackAction | str | None) -> CallStackAction | None:
    if value is None or isinstance(value, CallStackAction):
        return value
    return CallStackAction(value)
