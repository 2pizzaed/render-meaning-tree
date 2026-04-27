"""AST node predicate parser and evaluator.

The `ast_node` field in `constructs.yml` supports two compatible forms:

1. Legacy shorthand:

   - `"identifier"` matches a node whose `type` is `identifier`.
   - `["identifier", "int_literal"]` matches any listed node type.

2. Query object:

   - `{"query": [...]}` contains a non-empty list of predicate items.
   - Top-level query items are combined with AND.
   - An atomic item must contain `type`, where the value is either one type string
     or a non-empty list of type strings.
   - An atomic item may contain zero or one check operator. Supported checks are:
     `exists`, `equals`, `length`, and `contains`.
   - Logical items are `{"and": [...]}`, `{"or": [...]}`, and `{"not": item}`.
     `and` and `or` contain non-empty lists, while `not` contains exactly one item.

Example:

    ast_node:
      query:
        - type: program_entry_point
          exists: "body / [0]"
        - or:
            - type: call_expression
              contains:
                path: "arguments"
                value: null
            - type: command_expression
        - not:
            type: program_entry_point
            length:
              path: "body"
              equals: 0

Property paths use the same `property / [index]` format as the rest of the
project. A query matches when the provided `Node` satisfies the expression tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

from src.json_property_path import get_json_by_property_path
from src.types import Node

type AstNodeQuerySource = str | list[str] | dict[str, Any] | AstNodeQuery

_CHECK_OPERATORS = frozenset({"exists", "equals", "length", "contains"})
_LOGICAL_OPERATORS = frozenset({"and", "or", "not"})
_MISSING = object()


@dataclass(frozen=True, slots=True)
class AstNodeQuery:
    expression: AstNodeExpression

    @classmethod
    def from_raw(cls, data: AstNodeQuerySource) -> AstNodeQuery:
        if isinstance(data, AstNodeQuery):
            return data
        if isinstance(data, str):
            return cls(AstNodeExpression.atom((data,)))
        if isinstance(data, list):
            if not data:
                raise ValueError("ast_node list must not be empty")
            return cls(
                AstNodeExpression.logical(
                    "or",
                    tuple(AstNodeExpression.atom((_ensure_string(item, "ast_node item"),)) for item in data),
                )
            )
        if isinstance(data, dict):
            if set(data) != {"query"}:
                raise ValueError("ast_node query object must contain only the 'query' property")
            return cls(AstNodeExpression.logical("and", _parse_expression_list(data["query"], operation="query")))
        raise TypeError(f"Unsupported ast_node query {data!r}")

    def matches(self, node: Node) -> bool:
        return self.expression.matches(node)

    def duplicate_keys(self) -> tuple[tuple[Any, ...], ...]:
        return self.expression.duplicate_keys()


@dataclass(frozen=True, slots=True)
class AstNodeExpression:
    kind: Literal["atom", "and", "or", "not"]
    types: tuple[str, ...] = ()
    condition: AstNodeCondition | None = None
    children: tuple[AstNodeExpression, ...] = ()

    @classmethod
    def atom(cls, types: tuple[str, ...], condition: AstNodeCondition | None = None) -> AstNodeExpression:
        if not types:
            raise ValueError("ast_node query type list must not be empty")
        return cls(kind="atom", types=types, condition=condition)

    @classmethod
    def logical(
        cls,
        kind: Literal["and", "or", "not"],
        children: tuple[AstNodeExpression, ...],
    ) -> AstNodeExpression:
        if kind in {"and", "or"} and not children:
            raise ValueError(f"ast_node query {kind!r} requires a non-empty list")
        if kind == "not" and len(children) != 1:
            raise ValueError("ast_node query 'not' requires exactly one predicate")
        return cls(kind=kind, children=children)

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> AstNodeExpression:
        if not isinstance(data, dict):
            raise ValueError(f"ast_node query item must be an object, got {data!r}")

        logical_keys = [key for key in _LOGICAL_OPERATORS if key in data]
        if logical_keys:
            if len(logical_keys) != 1 or len(data) != 1:
                raise ValueError("ast_node logical query item must contain exactly one logical operator")
            operator = logical_keys[0]
            if operator == "not":
                payload = data[operator]
                if not isinstance(payload, dict):
                    raise ValueError("ast_node query 'not' requires an object predicate")
                return cls.logical("not", (cls.from_raw(payload),))
            binary_operator = cast(Literal["and", "or"], operator)
            return cls.logical(binary_operator, _parse_expression_list(data[operator], operation=operator))

        types = _parse_types(data.get("type"))
        condition_keys = [key for key in _CHECK_OPERATORS if key in data]
        if len(condition_keys) > 1:
            raise ValueError("ast_node query item can contain at most one check operator")

        allowed_keys = {"type", *condition_keys}
        extra_keys = set(data) - allowed_keys
        if extra_keys:
            raise ValueError(f"Unsupported ast_node query item keys: {sorted(extra_keys)!r}")

        condition = AstNodeCondition.from_raw(condition_keys[0], data[condition_keys[0]]) if condition_keys else None
        return cls.atom(types, condition)

    def matches(self, node: Node) -> bool:
        if self.kind == "atom":
            node_type = node.get("type")
            if not isinstance(node_type, str) or node_type not in self.types:
                return False
            return self.condition is None or self.condition.matches(node)
        if self.kind == "and":
            return all(child.matches(node) for child in self.children)
        if self.kind == "or":
            return any(child.matches(node) for child in self.children)
        if self.kind == "not":
            return not self.children[0].matches(node)
        raise ValueError(f"Unsupported ast_node expression kind {self.kind!r}")

    def duplicate_keys(self) -> tuple[tuple[Any, ...], ...]:
        if self.kind == "atom":
            condition_key = self.condition.key() if self.condition else None
            return tuple(("atom", node_type, condition_key) for node_type in self.types)
        if len(self.children) == 1:
            return self.children[0].duplicate_keys()
        if self.kind == "or":
            return tuple(key for child in self.children for key in child.duplicate_keys())
        return (("expression", self.key()),)

    def key(self) -> tuple[Any, ...]:
        if self.kind == "atom":
            return (
                self.kind,
                self.types,
                self.condition.key() if self.condition else None,
            )
        child_keys = tuple(sorted((child.key() for child in self.children), key=repr))
        return (self.kind, child_keys)


@dataclass(frozen=True, slots=True)
class AstNodeCondition:
    kind: str
    path: str
    value: Any = field(default=_MISSING)
    equals: int | None = None
    min: int | None = None
    max: int | None = None

    @classmethod
    def from_raw(cls, kind: str, payload: Any) -> AstNodeCondition:
        if kind == "exists":
            return cls(kind="exists", path=_parse_path_value(payload, operation="exists"))
        if kind == "equals":
            data = _ensure_dict(payload, operation="equals")
            return cls(
                kind="equals",
                path=_parse_path_value(data.get("path"), operation="equals"),
                value=data.get("value"),
            )
        if kind == "length":
            data = _ensure_dict(payload, operation="length")
            condition = cls(
                kind="length",
                path=_parse_path_value(data.get("path"), operation="length"),
                equals=_optional_int(data.get("equals"), field_name="length.equals"),
                min=_optional_int(data.get("min"), field_name="length.min"),
                max=_optional_int(data.get("max"), field_name="length.max"),
            )
            if condition.equals is None and condition.min is None and condition.max is None:
                raise ValueError("ast_node query 'length' requires equals, min, or max")
            return condition
        if kind == "contains":
            data = _ensure_dict(payload, operation="contains")
            return cls(
                kind="contains",
                path=_parse_path_value(data.get("path"), operation="contains"),
                value=data.get("value"),
            )
        raise ValueError(f"Unsupported ast_node query condition {kind!r}")

    def matches(self, node: Node) -> bool:
        resolved = get_json_by_property_path(node, self.path, default=_MISSING)
        if self.kind == "exists":
            return resolved is not _MISSING
        if self.kind == "equals":
            return resolved == self.value
        if self.kind == "length":
            return isinstance(resolved, list) and self._matches_length(len(resolved))
        if self.kind == "contains":
            return isinstance(resolved, list) and self.value in resolved
        raise ValueError(f"Unsupported ast_node condition kind {self.kind!r}")

    def key(self) -> tuple[Any, ...]:
        return (self.kind, self.path, _freeze_json(self.value), self.equals, self.min, self.max)

    def _matches_length(self, value: int) -> bool:
        if self.equals is not None and value != self.equals:
            return False
        if self.min is not None and value < self.min:
            return False
        return not (self.max is not None and value > self.max)


def _parse_expression_list(value: Any, *, operation: str) -> tuple[AstNodeExpression, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"ast_node query {operation!r} requires a non-empty list")
    return tuple(AstNodeExpression.from_raw(item) for item in value)


def _parse_types(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        if not value:
            raise ValueError("ast_node query type list must not be empty")
        return tuple(_ensure_string(item, "ast_node query type item") for item in value)
    raise ValueError("ast_node query item must contain type as a string or a non-empty list of strings")


def _parse_path_value(value: Any, *, operation: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"ast_node query {operation!r} requires a non-empty path")
    return value


def _ensure_dict(value: Any, *, operation: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"ast_node query {operation!r} requires an object payload")
    return value


def _ensure_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze_json(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value
