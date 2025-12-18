"""
Модуль для экспорта информации о назначенных значениях управляющих условий.

Предоставляет функцию для извлечения и экспорта информации о том, какие значения
(true/false) были назначены каким условиям при генерации трассы выполнения программы.
Также предоставляет функции для загрузки планов условий из JSON файлов.
"""

import json
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.cfg.abstractions import InterruptionType, OptionalBoolValue
from src.cfg.cfg import CFG, TraceAct
if 0:
    from src.cfg.trace_builder import TraceScenarioConfig

# Константа для унификации seed по умолчанию
DEFAULT_SEED = 59


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


def export_trace_acts(
    trace_acts: list[TraceAct], scenario_name: str = "default"
) -> dict[str, Any]:
    """Экспортирует полную трассу (список всех TraceAct) в удобный JSON-формат.

    Args:
        trace_acts: Список актов трассы выполнения программы
        scenario_name: Имя сценария трассировки (по умолчанию "default")

    Returns:
        Словарь с информацией о трассе:
        {
            "scenario_name": str,
            "trace": [
                {
                    "position_in_trace": int,
                    "ast_id": int | None,
                    "cfg_node_id": str | None,
                    "condition_value": str | None,
                    "button_type": str | None,
                    "is_known_correct": bool,
                    "incomplete_interruption": str | None,
                    "node_description": str | None,
                    "runtime_info": {
                        "function_name": str | None,
                        "function_args": dict | None,
                        "return_value": Any | None,
                        "print_outputs": list[str] | None,
                    } | None,
                },
                ...
            ]
        }
    """
    trace_items: list[dict[str, Any]] = []

    for position, trace_act in enumerate(trace_acts):
        # AST ID
        ast_id = None
        if (
            trace_act.wrapped_ast
            and isinstance(trace_act.wrapped_ast.ast_node, dict)
        ):
            ast_id = trace_act.wrapped_ast.ast_node.get("id")

        # CFG node info
        cfg_node_id = trace_act.cfg_node.id if trace_act.cfg_node else None
        node_description = (
            trace_act.cfg_node.describe() if trace_act.cfg_node else None
        )

        # Condition value
        condition_value_str: str | None
        if trace_act.condition_value is None:
            condition_value_str = None
        elif trace_act.condition_value == OptionalBoolValue.true:
            condition_value_str = "true"
        elif trace_act.condition_value == OptionalBoolValue.false:
            condition_value_str = "false"
        else:
            condition_value_str = str(trace_act.condition_value.value)

        # Incomplete interruption
        incomplete_interruption_str: str | None = None
        if (
            trace_act.incomplete_interruption
            and trace_act.incomplete_interruption != InterruptionType.NO_INTERRUPTION
        ):
            incomplete_interruption_str = str(
                trace_act.incomplete_interruption.value
                if hasattr(trace_act.incomplete_interruption, "value")
                else trace_act.incomplete_interruption
            )

        # Runtime info
        runtime_info_dict: dict[str, Any] | None = None
        if trace_act.runtime_info is not None:
            ri = trace_act.runtime_info
            runtime_info_dict = {}
            if ri.function_name is not None:
                runtime_info_dict["function_name"] = ri.function_name
            if ri.function_args is not None:
                # Преобразуем значения в JSON-совместимый формат
                runtime_info_dict["function_args"] = _safe_json_value(ri.function_args)
            if ri.return_value is not None:
                runtime_info_dict["return_value"] = _safe_json_value(ri.return_value)
            if ri.print_outputs is not None:
                runtime_info_dict["print_outputs"] = ri.print_outputs
            # Если словарь пустой, не добавляем его
            if not runtime_info_dict:
                runtime_info_dict = None

        item = {
            "position_in_trace": position,
            "ast_id": ast_id,
            "cfg_node_id": cfg_node_id,
            "condition_value": condition_value_str,
            "button_type": trace_act.button_type,
            "is_known_correct": trace_act.is_known_correct,
            "incomplete_interruption": incomplete_interruption_str,
        }
        
        if node_description:
            item["node_description"] = node_description
        
        if runtime_info_dict:
            item["runtime_info"] = runtime_info_dict

        trace_items.append(item)

    return {
        "scenario_name": scenario_name,
        "trace": trace_items,
    }


def _safe_json_value(value: Any) -> Any:
    """Преобразует значение в JSON-совместимый формат.
    
    Args:
        value: Значение для преобразования
        
    Returns:
        JSON-совместимое значение
    """
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_json_value(v) for k, v in value.items()}
    # Для остальных типов используем repr
    try:
        return repr(value)
    except Exception:
        return f"<{type(value).__name__}>"


def load_condition_plans(
    plan_source: str | Path | dict[str, Any]
) -> dict[str, Any]:
    """Загружает план условий из JSON файла или словаря.

    Поддерживает два формата:
    - Полный формат (экспортированный): содержит ast_id, cfg_node_id, condition_value, position_in_trace
    - Упрощённый формат: содержит только cfg_node_id и condition_value

    Также поддерживает файлы с несколькими сценариями (ключ "scenarios" со списком).

    Args:
        plan_source: Путь к JSON файлу, объект Path или словарь с данными плана

    Returns:
        Словарь с планом условий. Если файл содержит несколько сценариев,
        возвращает словарь с ключом "scenarios" (список) и опционально "seed".
        Если файл содержит один сценарий, возвращает словарь с ключом "scenario_name" и "conditions".

    Example:
        # Загрузка из файла
        plan = load_condition_plans("scenarios.json")

        # Загрузка из словаря
        plan = load_condition_plans({"scenario_name": "default", "conditions": [...]})
    """
    if isinstance(plan_source, (str, Path)):
        path = Path(plan_source)
        if not path.exists():
            raise FileNotFoundError(f"Plan file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = plan_source

    # Если это файл с несколькими сценариями
    if "scenarios" in data:
        return data

    # Если это один сценарий, нормализуем формат
    if "scenario_name" in data or "conditions" in data:
        return data

    raise ValueError(
        "Invalid plan format: expected 'scenarios' (list) or 'scenario_name'/'conditions' keys"
    )


def plan_to_scenario_config(
    plan: 'dict[str, Any] | TraceScenarioConfig', cfg: CFG, default_seed: int = DEFAULT_SEED
) -> "TraceScenarioConfig":
    """Преобразует план условий в TraceScenarioConfig.

    Преобразует план условий (словарь) в TraceScenarioConfig для использования
    при генерации трассы. Использует cfg_node_id для поиска узла в CFG и извлечения ast_id.

    Args:
        plan: Словарь с планом условий (результат load_condition_plans)
        cfg: Граф потока управления для поиска узлов
        default_seed: Seed по умолчанию, если не указан в плане

    Returns:
        TraceScenarioConfig с настроенными condition_sequences

    Raises:
        ValueError: Если план имеет неверный формат
    """
    from src.cfg.trace_builder import ConditionDecisionSchedule, TraceScenarioConfig

    # Извлекаем имя сценария
    scenario_name = plan.get("scenario_name", "default")

    # Извлекаем seed (может быть в корне плана или в сценарии)
    seed = plan.get("seed", default_seed)

    # Извлекаем условия
    conditions = plan.get("conditions", [])

    # Создаём словарь для группировки условий по ast_id
    # Ключ: ast_id, Значение: список значений условия в порядке появления
    condition_sequences: dict[int, list[bool]] = defaultdict(list)

    # Словарь для отслеживания cfg_node_id -> ast_id (для случаев, когда ast_id недоступен)
    cfg_to_ast: dict[str, int] = {}

    for condition in conditions:
        cfg_node_id = condition.get("cfg_node_id")
        condition_value_str = condition.get("condition_value")

        if not cfg_node_id or not condition_value_str:
            warnings.warn(
                f"Skipping condition without cfg_node_id or condition_value: {condition}",
                stacklevel=2,
            )
            continue

        # Преобразуем строковое значение в bool
        if condition_value_str == "true":
            condition_value = True
        elif condition_value_str == "false":
            condition_value = False
        else:
            warnings.warn(
                f"Unknown condition_value '{condition_value_str}', expected 'true' or 'false'",
                stacklevel=2,
            )
            continue

        # Пытаемся найти узел в CFG
        node = cfg.nodes.get(cfg_node_id)
        if not node:
            warnings.warn(
                f"CFG node '{cfg_node_id}' not found, skipping condition",
                stacklevel=2,
            )
            continue

        # Извлекаем ast_id из узла
        ast_id = None
        if (
            node.metadata
            and node.metadata.wrapped_ast
            and isinstance(node.metadata.wrapped_ast.ast_node, dict)
        ):
            ast_id = node.metadata.wrapped_ast.ast_node.get("id")

        if ast_id is None:
            # Если ast_id недоступен, используем cfg_node_id как ключ (но это не идеально)
            # Попробуем найти ast_id через другие условия, которые уже были обработаны
            if cfg_node_id in cfg_to_ast:
                ast_id = cfg_to_ast[cfg_node_id]
            else:
                warnings.warn(
                    f"AST ID not found for CFG node '{cfg_node_id}', skipping condition",
                    stacklevel=2,
                )
                continue

        # Сохраняем соответствие для будущего использования
        cfg_to_ast[cfg_node_id] = ast_id

        # Добавляем значение в последовательность для этого ast_id
        condition_sequences[ast_id].append(condition_value)

    # Преобразуем в формат ConditionDecisionSchedule
    schedule_dict: dict[int, ConditionDecisionSchedule] = {}
    for ast_id, values in condition_sequences.items():
        schedule_dict[ast_id] = ConditionDecisionSchedule(values=values)

    return TraceScenarioConfig(
        name=scenario_name,
        condition_sequences=schedule_dict,
        seed=seed,
    )


def load_scenarios_from_file(
    scenarios_file: str | Path, default_seed: int = DEFAULT_SEED
) -> list[dict[str, Any]]:
    """Загружает список сценариев из файла.

    Поддерживает два формата:
    1. Файл с одним сценарием: {"scenario_name": "...", "conditions": [...]}
    2. Файл с несколькими сценариями: {"seed": ..., "scenarios": [...]}

    Args:
        scenarios_file: Путь к JSON файлу со сценариями
        default_seed: Seed по умолчанию, если не указан в файле

    Returns:
        Список словарей с планами сценариев. Каждый словарь содержит:
        - scenario_name: имя сценария
        - conditions: список условий
        - seed: seed для этого сценария (если указан в корне файла)
    """
    path = Path(scenarios_file)
    if not path.exists():
        return []

    data = load_condition_plans(path)

    # Если это файл с несколькими сценариями
    if "scenarios" in data:
        file_seed = data.get("seed", default_seed)
        scenarios = []
        for scenario in data["scenarios"]:
            # Добавляем seed в каждый сценарий, если он не указан явно
            if "seed" not in scenario:
                scenario = {**scenario, "seed": file_seed}
            scenarios.append(scenario)
        return scenarios

    # Если это один сценарий, возвращаем список с одним элементом
    if "scenario_name" in data or "conditions" in data:
        if "seed" not in data:
            data = {**data, "seed": default_seed}
        return [data]

    return []

