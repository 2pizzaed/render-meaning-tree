"""Values of situation objects for explanation template paths (``${X.prop}``, ``${X->rel.prop}``).

The reasoner's variable snapshots carry only object names and metadata, so a path
interpolation is resolved against LOQI texts: the situation supplies property
values, relationship links and object ``localizedName`` metadata, the domain model
supplies the ``localizedName`` of enum values (``InterruptionType:break`` ->
«прерывание цикла»).

Only what explanation templates need is parsed: scalar properties, one-target
relationship links and ``localizedName`` metadata of ``obj`` declarations, and
``localizedName`` metadata of ``enum`` values. The situation is usually the
specific domain exported *after* reasoning, so values of properties and links
that the graph changes are the final ones, not the ones at the conclude node.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_STRING = r'"(?:[^"\\]|\\.)*"'
_COMMENT_RE = re.compile(rf"({_STRING})|//[^\n]*")
_OBJECT_RE = re.compile(
    r"^\s*(?:var\s+\w+\s*=\s*)?obj\s+(?P<name>\w+)\s*:\s*\w+\s*\{(?P<body>.*?)^\s*\}"
    rf"(?:\s*\[(?P<metadata>(?:[^\]\"]|{_STRING})*)\])?",
    re.MULTILINE | re.DOTALL,
)
_PROPERTY_RE = re.compile(r"^\s*(?P<name>\w+)\s*=\s*(?P<value>[^;\n]+?)\s*;", re.MULTILINE)
_RELATIONSHIP_RE = re.compile(
    rf"^\s*(?P<name>\w+)\s*\((?P<targets>[^)]*)\)\s*(?:\[(?:[^\]\"]|{_STRING})*\]\s*)?;",
    re.MULTILINE,
)
_ENUM_LITERAL_RE = re.compile(r"\A(?P<enum>\w+):(?P<value>`[^`]+`|\w+)\Z")
_ENUM_RE = re.compile(r"\benum\s+(?P<name>\w+)\s*\{(?P<body>.*?)\}", re.DOTALL)
_ENUM_VALUE_RE = re.compile(r"(?P<name>`[^`]+`|\w+)\s*(?:\[(?P<metadata>[^\]]*)\])?\s*(?:,|\Z)")
_LOCALIZED_NAME_RE = re.compile(r'\b(?P<loc>\w+)\.localizedName\s*=\s*"(?P<value>(?:[^"\\]|\\.)*)"')


@dataclass(frozen=True, slots=True)
class EnumLiteral:
    enum: str
    value: str


type LoqiScalar = EnumLiteral | str


@dataclass(slots=True)
class LoqiObjectValues:
    """What templates can read from one ``obj`` declaration."""

    properties: dict[str, LoqiScalar] = field(default_factory=dict)
    relationships: dict[str, list[str]] = field(default_factory=dict)
    """Targets of one-target links (``rel(x);``), in declaration order, without repeats."""
    localized_names: dict[str, str] = field(default_factory=dict)
    """``{LOC: localizedName}`` from the object's metadata."""


def parse_objects(situation_loqi: str) -> dict[str, LoqiObjectValues]:
    """``{object name: values}`` for the ``obj`` declarations of a situation."""
    objects: dict[str, LoqiObjectValues] = {}
    for obj in _OBJECT_RE.finditer(_strip_comments(situation_loqi)):
        values = LoqiObjectValues(
            properties={
                prop["name"]: _scalar(prop["value"]) for prop in _PROPERTY_RE.finditer(obj["body"])
            },
            localized_names=_localized_names(obj["metadata"] or ""),
        )
        for link in _RELATIONSHIP_RE.finditer(obj["body"]):
            targets = [target.strip().strip("`") for target in link["targets"].split(",")]
            if len(targets) != 1 or not targets[0]:
                continue  # n-ary links (isBetween(a, b)) are not navigable with ->
            linked = values.relationships.setdefault(link["name"], [])
            if targets[0] not in linked:
                linked.append(targets[0])
        objects[obj["name"]] = values
    return objects


def parse_object_properties(situation_loqi: str) -> dict[str, dict[str, LoqiScalar]]:
    """``{object name: {property: value}}`` for the ``obj`` declarations of a situation."""
    return {name: values.properties for name, values in parse_objects(situation_loqi).items()}


def parse_enum_localized_names(domain_loqi: str) -> dict[str, dict[str, dict[str, str]]]:
    """``{enum: {value: {LOC: localizedName}}}`` from the enum declarations of a domain."""
    enums: dict[str, dict[str, dict[str, str]]] = {}
    for enum in _ENUM_RE.finditer(_strip_comments(domain_loqi)):
        values: dict[str, dict[str, str]] = {}
        for value in _ENUM_VALUE_RE.finditer(enum["body"].strip()):
            values[value["name"].strip("`")] = _localized_names(value["metadata"] or "")
        enums[enum["name"]] = values
    return enums


class LoqiPropertyResolver:
    """Resolves ``(object name, relationships, property, loc code)`` to the text a template shows.

    Relationships are followed one by one (``X->rel->rel2``); each must lead to
    exactly one object, otherwise the path is unresolved. The path then ends
    either with a property — an enum value becomes its ``localizedName`` in the
    requested localization (falling back to the bare value), any other scalar
    its LOQI text — or, without a property, with the reached object's
    ``localizedName``.
    """

    def __init__(self, situation_loqi: str, domain_loqi: str = "") -> None:
        self._objects = parse_objects(situation_loqi)
        self._enum_names = parse_enum_localized_names(domain_loqi)

    def __call__(
        self,
        object_name: str,
        relationships: tuple[str, ...],
        property_name: str | None,
        loc_code: str,
    ) -> str | None:
        obj = self._objects.get(object_name)
        for relationship in relationships:
            targets = obj.relationships.get(relationship, []) if obj is not None else []
            if len(targets) != 1:
                return None  # no link or an ambiguous one
            obj = self._objects.get(targets[0])
        if obj is None:
            return None
        if property_name is None:
            return obj.localized_names.get(loc_code.upper())
        value = obj.properties.get(property_name)
        if value is None:
            return None
        if isinstance(value, EnumLiteral):
            names = self._enum_names.get(value.enum, {}).get(value.value, {})
            return names.get(loc_code.upper(), value.value)
        return value


def _localized_names(metadata: str) -> dict[str, str]:
    return {
        name["loc"].upper(): _unescape(name["value"])
        for name in _LOCALIZED_NAME_RE.finditer(metadata)
    }


def _scalar(raw: str) -> LoqiScalar:
    if (literal := _ENUM_LITERAL_RE.match(raw)) is not None:
        return EnumLiteral(literal["enum"], literal["value"].strip("`"))
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return _unescape(raw[1:-1])
    return raw


def _unescape(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", text)


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(lambda match: match.group(1) or "", text)
