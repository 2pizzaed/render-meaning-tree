"""Minimal string-interpolation for explanation templates.

A deliberately tiny, regex-based port of the *interpolation* layer of the
`JavaStringTemplating <../../../../JavaStringTemplating>`_ library (``Template`` /
``InterpretationData``). Supported surface forms:

* **simple interpolation** — ``$name`` (a bare variable reference);
* **braced interpolation** — ``${name}`` (the same, allowing surrounding text to
  abut the name, e.g. ``${name}s``), or a path from a variable: relationships
  (LOQI ``->``) optionally followed by a property — ``${name.prop}``,
  ``${name->rel}``, ``${name->rel->rel2.prop}``. A path is looked up in the
  supplied values under its full text (e.g. ``"name->rel.prop"``); callers
  resolve it themselves (see :func:`split_reference`);
* **modifiers** — ``${name}[mod, mod='arg', mod('arg', 2)]`` right after a braced
  interpolation (no space before ``[``), applied left to right to the substituted
  text. As in the Java lexer, ``$name[...]`` is *not* a modifier: the brackets stay
  plain text.

A leading backslash escapes the dollar (``\\$`` -> literal ``$``), matching the
Java lexer's ``STR: (~[$] | '\\$')+`` rule.

The full Java expression language inside ``${...}`` (arithmetic, comparisons,
method calls) is intentionally **not** ported: braced content
that is not a plain reference, references that are not supplied, and
unknown modifiers are left verbatim rather than evaluated or blanked. This keeps
explanation rendering robust — an unknown ``$foo`` stays visible instead of
crashing or silently vanishing.

Identifier spelling follows the Java grammar (``Letter = [a-zA-Z$_]``): a name
starts with ``[A-Za-z_$]`` and continues with ``[A-Za-z0-9_$]``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

_IDENTIFIER = r"[A-Za-z_$][A-Za-z0-9_$]*"
_STRING = r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\""
_LITERAL = rf"{_STRING}|\d+(?:\.\d+)?|{_IDENTIFIER}"  # identifiers: true / false / null

# One pass, first-match-wins alternation: escaped dollar, then ${...}[...], then $name.
_TOKEN = re.compile(
    r"\\\$"  # escaped dollar -> literal '$'
    rf"|\$\{{(?P<braced>[^{{}}]*)\}}"  # ${ ... } (non-nested content)
    rf"(?:\[(?P<modifiers>(?:[^\]'\"]|{_STRING})*)\])?"  # optional [modifiers]
    rf"|\$(?P<simple>{_IDENTIFIER})"  # $name
)

# Braced content that is interpolated: a variable, optionally followed by
# relationships (``->rel``) and a property (``.prop``).
_REFERENCE_RE = re.compile(
    rf"\A(?P<name>{_IDENTIFIER})(?P<relationships>(?:->{_IDENTIFIER})*)(?:\.(?P<prop>{_IDENTIFIER}))?\Z"
)

# Java TemplatingParser: mod (',' mod)* ','?  where
# mod: ID | ID '=' literal | ID '(' (literal ',')* literal? ')'.
_ARGS = rf"(?:(?:{_LITERAL})\s*(?:,\s*(?:{_LITERAL})\s*)*,?\s*)?"


def _modifier_pattern(name: str = "", value: str = "", args: str = "") -> str:
    return (
        rf"\s*({name}{_IDENTIFIER})\s*"
        rf"(?:=\s*({value}{_LITERAL})\s*|\(\s*({args}{_ARGS})\)\s*)?"
    )


_MODIFIER_RE = re.compile(_modifier_pattern("?P<name>", "?P<value>", "?P<args>"))
_MODIFIERS_RE = re.compile(rf"{_modifier_pattern()}(?:,{_modifier_pattern()})*,?\s*")
_LITERAL_RE = re.compile(_LITERAL)

_JAVA_ESCAPES = {"b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r"}

type Modifier = Callable[..., str]
"""A template modifier: ``(text, *literal_args) -> text``."""


def case_modifier(text: str, _case: object = None) -> str:
    """``[case='р']`` — Russian declension of the substituted name.

    Declension is not implemented yet: the text stays in the nominative case.
    """
    return text


DEFAULT_MODIFIERS: Mapping[str, Modifier] = {"case": case_modifier}


def interpolate(
    template: str,
    variables: Mapping[str, Any],
    modifiers: Mapping[str, Modifier] = DEFAULT_MODIFIERS,
) -> str:
    """Replace ``$name`` / ``${name}[modifiers]`` interpolations in ``template``.

    Each interpolation is substituted with ``str(variables[name])`` (for a path
    like ``${name->rel.prop}`` — ``str(variables["name->rel.prop"])``) and then run through its
    modifiers (looked up in ``modifiers``). Braced interpolations are stripped of
    surrounding whitespace before lookup (``${ name }`` == ``${name}``). A ``\\$``
    escape becomes a literal ``$``.

    Substitution is single-pass: values inserted into the result are never
    rescanned, so a value that itself contains ``$name`` is left as-is.

    Anything that cannot be resolved is preserved verbatim, modifiers included: a
    missing variable, braced content that is not a plain reference (e.g. an
    expression like ``${3+3}``), or an unknown modifier (or one rejecting its
    arguments). Brackets that are not valid modifier syntax are not modifiers:
    they stay plain text after the substituted value.
    """

    def _replace(match: re.Match[str]) -> str:
        text = match.group()
        if text == "\\$":
            return "$"
        name = match.group("braced")
        if name is not None:
            name = name.strip()
            if not _REFERENCE_RE.match(name):
                return text  # not a plain reference — leave the expression untouched
        else:
            name = match.group("simple")
        if name not in variables:
            return text  # unknown variable — keep the placeholder visible
        value = str(variables[name])

        raw_modifiers = match.group("modifiers")
        if raw_modifiers is None:
            return value
        calls = _parse_modifiers(raw_modifiers)
        if calls is None:
            # not modifier syntax — the brackets are ordinary template text
            return f"{value}[{interpolate(raw_modifiers, variables, modifiers)}]"
        for modifier_name, args in calls:
            modifier = modifiers.get(modifier_name)
            if modifier is None:
                return text  # unknown modifier — keep the placeholder visible
            try:
                value = modifier(value, *args)
            except TypeError:
                return text  # wrong arguments for the modifier
        return value

    return _TOKEN.sub(_replace, template)


def split_reference(reference: str) -> tuple[str, tuple[str, ...], str | None]:
    """``"name->rel->rel2.prop"`` -> ``("name", ("rel", "rel2"), "prop")``.

    ``reference`` must be one of :func:`referenced_variables`.
    """
    match = _REFERENCE_RE.match(reference)
    if match is None:
        raise ValueError(f"not a template reference: {reference!r}")
    relationships = tuple(filter(None, match.group("relationships").split("->")))
    return match.group("name"), relationships, match.group("prop")


def referenced_variables(template: str) -> set[str]:
    """References that ``template`` interpolates: ``name`` or a path like ``name->rel.prop``."""
    names: set[str] = set()
    for match in _TOKEN.finditer(template):
        name = match.group("braced")
        name = name.strip() if name is not None else match.group("simple")
        if name is not None and _REFERENCE_RE.match(name):
            names.add(name)
    return names


def _parse_modifiers(content: str) -> list[tuple[str, tuple[Any, ...]]] | None:
    """Parse ``mod, mod='x', mod('x', 1)`` into ``[(name, args), ...]``.

    Returns ``None`` when ``content`` is not valid modifier syntax.
    """
    if not _MODIFIERS_RE.fullmatch(content):
        return None
    calls: list[tuple[str, tuple[Any, ...]]] = []
    for match in _MODIFIER_RE.finditer(content):
        if match.group("value") is not None:
            args: tuple[Any, ...] = (_literal(match.group("value")),)
        elif match.group("args") is not None:
            args = tuple(_literal(arg.group()) for arg in _LITERAL_RE.finditer(match.group("args")))
        else:
            args = ()
        calls.append((match.group("name"), args))
    return calls


def _literal(token: str) -> Any:
    """A modifier argument literal (Java ``literal`` rule) as a Python value."""
    if token[0] in "'\"":
        return re.sub(r"\\(.)", lambda m: _JAVA_ESCAPES.get(m.group(1), m.group(1)), token[1:-1])
    if token[0].isdigit():
        return float(token) if "." in token else int(token)
    return {"true": True, "false": False, "null": None}.get(token, token)
