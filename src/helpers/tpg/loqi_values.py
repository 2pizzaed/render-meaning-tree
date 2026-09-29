"""Property values of situation objects for explanation templates (``${X.prop}``).

The reasoner's variable snapshots carry only object names and metadata, so a
``${X.prop}`` interpolation is resolved against LOQI texts: the situation supplies
the property value and the domain model supplies the ``localizedName`` of enum
values (``InterruptionType:break`` -> «прерывание цикла»).

Only what explanation templates need is parsed: scalar properties of ``obj``
declarations and ``localizedName`` metadata of ``enum`` values. The situation is
usually the specific domain exported *after* reasoning, so values of properties
that the graph changes are the final ones, not the ones at the conclude node.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_COMMENT_RE = re.compile(r'("(?:[^"\\]|\\.)*")|//[^\n]*')
_OBJECT_RE = re.compile(
    r"^\s*(?:var\s+\w+\s*=\s*)?obj\s+(?P<name>\w+)\s*:\s*\w+\s*\{(?P<body>.*?)^\s*\}",
    re.MULTILINE | re.DOTALL,
)
_PROPERTY_RE = re.compile(r"^\s*(?P<name>\w+)\s*=\s*(?P<value>[^;\n]+?)\s*;", re.MULTILINE)
_ENUM_LITERAL_RE = re.compile(r"\A(?P<enum>\w+):(?P<value>`[^`]+`|\w+)\Z")
_ENUM_RE = re.compile(r"\benum\s+(?P<name>\w+)\s*\{(?P<body>.*?)\}", re.DOTALL)
_ENUM_VALUE_RE = re.compile(r"(?P<name>`[^`]+`|\w+)\s*(?:\[(?P<metadata>[^\]]*)\])?\s*(?:,|\Z)")
_LOCALIZED_NAME_RE = re.compile(r'\b(?P<loc>\w+)\.localizedName\s*=\s*"(?P<value>(?:[^"\\]|\\.)*)"')


@dataclass(frozen=True, slots=True)
class EnumLiteral:
    enum: str
    value: str


type LoqiScalar = EnumLiteral | str


def parse_object_properties(situation_loqi: str) -> dict[str, dict[str, LoqiScalar]]:
    """``{object name: {property: value}}`` for the ``obj`` declarations of a situation."""
    objects: dict[str, dict[str, LoqiScalar]] = {}
    for obj in _OBJECT_RE.finditer(_strip_comments(situation_loqi)):
        objects[obj["name"]] = {
            prop["name"]: _scalar(prop["value"]) for prop in _PROPERTY_RE.finditer(obj["body"])
        }
    return objects


def parse_enum_localized_names(domain_loqi: str) -> dict[str, dict[str, dict[str, str]]]:
    """``{enum: {value: {LOC: localizedName}}}`` from the enum declarations of a domain."""
    enums: dict[str, dict[str, dict[str, str]]] = {}
    for enum in _ENUM_RE.finditer(_strip_comments(domain_loqi)):
        values: dict[str, dict[str, str]] = {}
        for value in _ENUM_VALUE_RE.finditer(enum["body"].strip()):
            values[value["name"].strip("`")] = {
                name["loc"].upper(): _unescape(name["value"])
                for name in _LOCALIZED_NAME_RE.finditer(value["metadata"] or "")
            }
        enums[enum["name"]] = values
    return enums


class LoqiPropertyResolver:
    """Resolves ``(object name, property, loc code)`` to the text a template shows.

    An enum value becomes its ``localizedName`` in the requested localization
    (falling back to the bare value), any other scalar its LOQI text.
    """

    def __init__(self, situation_loqi: str, domain_loqi: str = "") -> None:
        self._properties = parse_object_properties(situation_loqi)
        self._enum_names = parse_enum_localized_names(domain_loqi)

    def __call__(self, object_name: str, property_name: str, loc_code: str) -> str | None:
        value = self._properties.get(object_name, {}).get(property_name)
        if value is None:
            return None
        if isinstance(value, EnumLiteral):
            names = self._enum_names.get(value.enum, {}).get(value.value, {})
            return names.get(loc_code.upper(), value.value)
        return value


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
