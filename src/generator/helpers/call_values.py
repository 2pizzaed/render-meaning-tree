"""Пункты dropdown значений вызова у кнопок step-out.

Кнопка END размеченного вызова открывает dropdown: студент выбирает, из какого вызова
функции он возвращается (``docs/ideas/function_return_dropdown.md``). Каждый пункт -
отдельный ответ с ``domainInfo`` ``<END кнопки>,<значение END>``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.generator.helpers.ui_trace import resolve_button_action
from src.generator.registry import SituationRegistry
from src.model.situation import Action, Construct, SemanticValue
from src.serialization.loqi import LoqiSerializer


@dataclass(frozen=True, slots=True)
class CallValueOption:
    answer_id: int
    # «<имя END>,<имя SemanticValue>»: в LOQI-именах запятых нет.
    domain_info: str
    hint: str
    # BEGIN места вызова, которому принадлежит значение: по актам трассы этого BEGIN
    # фрагмент кода проверяет, начат ли вызов.
    begin_name: str


def call_value_menus(
    registry: SituationRegistry,
    buttons: list[dict[str, Any]],
    serializer: LoqiSerializer,
) -> dict[int, tuple[CallValueOption, ...]]:
    """Пункты dropdown по номеру ответа кнопки END размеченного вызова.

    Пункты - значения с подсказками у END всех размеченных мест вызова той же функции.
    Номера ответов пунктов идут после номеров кнопок.
    """
    action_ids = [int(button["action_id"]) for button in buttons if button.get("action_id") is not None]
    next_answer_id = max(action_ids, default=-1) + 1
    menus: dict[int, tuple[CallValueOption, ...]] = {}
    for button in buttons:
        action_id = button.get("action_id")
        if action_id is None:
            continue
        try:
            end = resolve_button_action(registry, button)
        except LookupError:
            # Кнопку с неоднозначным действием пропускают и ответы.
            continue
        if end is None or not is_annotated_call_end(end):
            continue
        options: list[CallValueOption] = []
        for call_end in _annotated_call_ends(registry, _called_function(end.parent)):
            begin_name = serializer.object_name(call_end.parent.begin_action())
            for value in call_end.values:
                domain_info = call_value_domain_info(serializer, end, value)
                if domain_info is None or begin_name is None:
                    continue
                options.append(
                    CallValueOption(
                        answer_id=next_answer_id,
                        domain_info=domain_info,
                        hint=value.hint,
                        begin_name=begin_name,
                    )
                )
                next_answer_id += 1
        if options:
            menus[int(action_id)] = tuple(options)
    return menus


def call_value_domain_info(
    serializer: LoqiSerializer, end: Action, value: SemanticValue
) -> str | None:
    """``domainInfo`` пункта «END и значение»; None, если пункта нет (значение без подсказки)."""
    end_name = serializer.object_name(end)
    value_name = serializer.object_name(value)
    if not value.hint or end_name is None or value_name is None:
        return None
    return f"{end_name},{value_name}"


def is_annotated_call_end(action: Action) -> bool:
    return (
        action.rule.role == "END"
        and action.annotation is not None
        and "call" in action.parent.rule.kind_classes
    )


def _annotated_call_ends(registry: SituationRegistry, function_id: int | None) -> list[Action]:
    return [
        action
        for action in registry.all_actions()
        if is_annotated_call_end(action) and _called_function(action.parent) == function_id
    ]


def _called_function(call: Construct) -> int | None:
    """Узел определения функции: на него указывает действие ``func`` вызова."""
    return next((action.ast_id for action in call.action_by_role("func")), None)
