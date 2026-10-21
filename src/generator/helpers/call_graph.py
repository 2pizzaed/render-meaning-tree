"""Граф вызовов пользовательских функций ситуации."""

from __future__ import annotations

from dataclasses import dataclass

from src.generator.helpers.trace_features import is_function_construct
from src.generator.registry import SituationRegistry
from src.model.situation import Construct


@dataclass(frozen=True, slots=True)
class CallSite:
    # Конструкт func_call_structure.
    call: Construct
    # Ближайшая объемлющая функция или корень программы.
    caller: Construct
    # Функция, в которую раскрывается действие func вызова.
    callee: Construct


def call_graph(registry: SituationRegistry) -> list[CallSite]:
    """Места вызова пользовательских функций.

    Связь «вызов -> определение» уже построена генератором: конструкт вызова есть
    только у пользовательской функции, а его действие func раскрывается в её конструкт.
    """
    ast = registry.code.ast
    sites: list[CallSite] = []
    for construct in registry.constructs.values():
        if "call" not in construct.rule.kind_classes:
            continue
        callee = next(
            (
                target
                for action in construct.actions
                if (target := action.expands_to()) is not None
                and is_function_construct(ast, target)
            ),
            None,
        )
        if callee is not None:
            sites.append(CallSite(construct, enclosing_function(registry, construct), callee))
    return sites


def enclosing_function(registry: SituationRegistry, construct: Construct) -> Construct:
    """Ближайшая объемлющая функция конструкта или корень программы."""
    current = construct
    while current.parent is not None:
        current = current.parent
        if is_function_construct(registry.code.ast, current):
            return current
    return current


def function_name(function: Construct) -> str:
    declaration = function.ast_node.get("declaration")
    name = declaration.get("name") if isinstance(declaration, dict) else None
    value = name.get("name") if isinstance(name, dict) else None
    return value if isinstance(value, str) else f"#{function.ast_id}"


def recursive_functions(sites: list[CallSite]) -> set[int]:
    """AST id функций, лежащих на цикле графа вызовов (включая взаимную рекурсию)."""
    callees: dict[int, set[int]] = {}
    for site in sites:
        callees.setdefault(site.caller.ast_id, set()).add(site.callee.ast_id)

    def reaches(start: int, target: int) -> bool:
        seen: set[int] = set()
        stack = list(callees.get(start, ()))
        while stack:
            current = stack.pop()
            if current == target:
                return True
            if current not in seen:
                seen.add(current)
                stack.extend(callees.get(current, ()))
        return False

    return {function for function in callees if reaches(function, function)}
