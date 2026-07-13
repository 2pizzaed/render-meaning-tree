"""Minimal string-interpolation for explanation templates.

A deliberately tiny, regex-based port of the *interpolation* layer of the
`JavaStringTemplating <../../../../JavaStringTemplating>`_ library (``Template`` /
``InterpretationData``). Only the two surface forms are supported:

* **simple interpolation** — ``$name`` (a bare variable reference);
* **braced interpolation** — ``${name}`` (the same, allowing surrounding text to
  abut the name, e.g. ``${name}s``).

A leading backslash escapes the dollar (``\\$`` -> literal ``$``), matching the
Java lexer's ``STR: (~[$] | '\\$')+`` rule.

The full Java expression language inside ``${...}`` (arithmetic, comparisons,
field access, method calls, modifiers) is intentionally **not** ported: braced
content that is not a plain identifier, and references to variables that are not
supplied, are left verbatim rather than evaluated or blanked. This keeps
explanation rendering robust — an unknown ``$foo`` stays visible instead of
crashing or silently vanishing.

Identifier spelling follows the Java grammar (``Letter = [a-zA-Z$_]``): a name
starts with ``[A-Za-z_$]`` and continues with ``[A-Za-z0-9_$]``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_IDENTIFIER = r"[A-Za-z_$][A-Za-z0-9_$]*"

# One pass, first-match-wins alternation: escaped dollar, then ${...}, then $name.
_TOKEN = re.compile(
    r"\\\$"  # escaped dollar -> literal '$'
    rf"|\$\{{(?P<braced>[^{{}}]*)\}}"  # ${ ... } (non-nested content)
    rf"|\$(?P<simple>{_IDENTIFIER})"  # $name
)

_IDENTIFIER_RE = re.compile(rf"\A{_IDENTIFIER}\Z")


def interpolate(template: str, variables: Mapping[str, Any]) -> str:
    """Replace ``$name`` / ``${name}`` interpolations in ``template``.

    Each interpolation is substituted with ``str(variables[name])``. Braced
    interpolations are stripped of surrounding whitespace before lookup
    (``${ name }`` == ``${name}``). A ``\\$`` escape becomes a literal ``$``.

    Substitution is single-pass: values inserted into the result are never
    rescanned, so a value that itself contains ``$name`` is left as-is.

    Anything the simple form cannot resolve is preserved verbatim: a missing
    variable, or braced content that is not a plain identifier (e.g. an
    expression like ``${3+3}``), keeps its original ``$...`` text.
    """

    def _replace(match: re.Match[str]) -> str:
        text = match.group()
        if text == "\\$":
            return "$"
        name = match.group("braced")
        if name is not None:
            name = name.strip()
            if not _IDENTIFIER_RE.match(name):
                return text  # not a bare variable — leave the expression untouched
        else:
            name = match.group("simple")
        if name not in variables:
            return text  # unknown variable — keep the placeholder visible
        return str(variables[name])

    return _TOKEN.sub(_replace, template)
