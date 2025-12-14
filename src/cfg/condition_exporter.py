"""
Модуль для экспорта информации о назначенных значениях управляющих условий.

Предоставляет функцию для извлечения и экспорта информации о том, какие значения
(true/false) были назначены каким условиям при генерации трассы выполнения программы.
"""

from typing import Any

from src.cfg.abstractions import OptionalBoolValue
from src.cfg.cfg import TraceAct


def export_condition_decisions(
    trace_acts: list[TraceAct], scenario_name: str = "default"
) -> dict[str, Any]:
    """Извлекает информацию о назначенных значениях условий из трассы.

    Собирает все акты трассы, которые являются условиями (имеют condition_value != None),
    и формирует структурированные данные для экспорта в JSON.

    Args:
        trace_acts: Список актов трассы выполнения программы
        scenario_name: Имя сценария трассировки (по умолчанию "default")

    Returns:
        Словарь с информацией о назначенных значениях условий:
        {
            "scenario_name": str,
            "conditions": [
                {
                    "ast_id": int,
                    "condition_value": str,  # "true" или "false"
                    "position_in_trace": int,
                    "cfg_node_id": str,
                    "node_description": str
                },
                ...
            ]
        }
    """
    conditions = []

    for position, trace_act in enumerate(trace_acts):
        # Пропускаем акты без значения условия
        if trace_act.condition_value is None:
            continue

        # Извлекаем AST ID
        ast_id = None
        if (
            trace_act.wrapped_ast
            and isinstance(trace_act.wrapped_ast.ast_node, dict)
        ):
            ast_id = trace_act.wrapped_ast.ast_node.get("id")

        # Преобразуем значение условия в строку
        condition_value_str = None
        if trace_act.condition_value == OptionalBoolValue.true:
            condition_value_str = "true"
        elif trace_act.condition_value == OptionalBoolValue.false:
            condition_value_str = "false"
        else:
            # Если значение не true/false, используем строковое представление
            condition_value_str = str(trace_act.condition_value.value)

        # Получаем описание узла
        node_description = None
        if trace_act.cfg_node:
            node_description = trace_act.cfg_node.describe()

        condition_info = {
            "ast_id": ast_id,
            "condition_value": condition_value_str,
            "position_in_trace": position,
            "cfg_node_id": trace_act.cfg_node.id if trace_act.cfg_node else None,
        }

        # Добавляем описание узла, если оно доступно
        if node_description:
            condition_info["node_description"] = node_description

        conditions.append(condition_info)

    return {
        "scenario_name": scenario_name,
        "conditions": conditions,
    }

