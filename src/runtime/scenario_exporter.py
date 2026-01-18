"""
Экспорт результатов runtime трассировки в формат сценариев.

Создаёт JSON-файлы сценариев, совместимые с TraceScenarioConfig,
на основе реального выполнения программы.

Формат сценария:
{
    "scenario_name": "default",
    "events": [
        {
            "type": "condition",
            "ast_id": 16,
            "value": "true",
            "order": 1,
            "line_number": 3,
            "expression_text": "x > 0"
        },
        {
            "type": "function_call",
            "ast_id": 15,
            "function_name": "factorial",
            "args": {"n": 5},
            "order": 2,
            "line_number": 5,
            "call_line": 5
        },
        {
            "type": "function_return",
            "ast_id": 18,
            "function_name": "factorial",
            "return_value": 120,
            "order": 3,
            "line_number": 4
        }
    ],
    "conditions": [...]  // Для обратной совместимости
}
"""

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.runtime.models import (
    ConditionEvaluation,
    FunctionCall,
    FunctionReturn,
    RuntimeTrace,
)

if TYPE_CHECKING:
    from src.ast_analyzer import ASTNodeAnalyzer


def _find_ast_id_for_event(
    event: FunctionCall | FunctionReturn,
    event_type: str,
    ast_analyzer: 'ASTNodeAnalyzer | None' = None,
) -> int | None:
    """Находит ast_id для события вызова или возврата функции.
    
    Args:
        event: Событие FunctionCall или FunctionReturn
        event_type: Тип события ("function_call" или "function_return")
        ast_analyzer: Анализатор AST для поиска узлов (опционально)
        
    Returns:
        ast_id узла или None, если не найден
    """
    if ast_analyzer is None:
        return None
    
    # Определяем тип узла и номер строки для поиска
    if event_type == "function_call":
        node_type = "function_call"
        search_line = event.call_line if hasattr(event, 'call_line') and event.call_line else event.line_number
    elif event_type == "function_return":
        node_type = "return_statement"
        search_line = event.line_number
    else:
        return None
    
    if search_line is None:
        return None
    
    # Ищем все узлы указанного типа на этой строке
    candidates = []
    for ast_id, node in ast_analyzer.nodes_cache.items():
        node_type_found = node.get('type', '')
        if node_type_found == node_type:
            node_line = ast_analyzer.get_code_line_number_by_id(ast_id)
            if node_line == search_line:
                candidates.append((ast_id, node))
    
    # Если на строке несколько узлов, используем первый найденный
    # В будущем можно улучшить логику сопоставления (например, по имени функции)
    if candidates:
        return candidates[0][0]
    
    return None


def export_scenario_from_trace(
    trace: RuntimeTrace,
    scenario_name: str = "default",
    ast_analyzer: "ASTNodeAnalyzer | None" = None,
) -> dict[str, Any]:
    """Создаёт сценарий из трассы выполнения.
    
    Сохраняет все события (условия, вызовы, возвраты) в единый список events
    с ast_id для всех типов событий.
    
    Args:
        trace: Трасса выполнения с событиями
        scenario_name: Имя сценария
        ast_analyzer: Анализатор AST для получения ast_id (опционально)
        
    Returns:
        Словарь сценария для сериализации в JSON с полями:
        - scenario_name: имя сценария
        - events: список всех событий в порядке выполнения
        - conditions: список условий (для обратной совместимости)
    """
    events = []
    conditions = []  # Для обратной совместимости
    
    # Собираем все события в порядке выполнения
    for event in trace.events:
        event_data: dict[str, Any] = {
            "order": event.order,
            "line_number": event.line_number,
        }
        
        if isinstance(event, ConditionEvaluation):
            event_data.update({
                "type": "condition",
                "ast_id": event.ast_id,
                "value": "true" if event.value else "false",
            })
            
            # Опциональные поля
            if event.expression_text:
                event_data["expression_text"] = event.expression_text
            if event.condition_type:
                event_data["condition_type"] = event.condition_type
            
            events.append(event_data)
            
            # Также добавляем в conditions для обратной совместимости
            conditions.append({
                "ast_id": event.ast_id,
                "condition_value": event_data["value"],
                "line_number": event.line_number,
                "order": event.order,
                **({} if not event.expression_text else {"expression_text": event.expression_text}),
                **({} if not event.condition_type else {"condition_type": event.condition_type}),
            })
        
        elif isinstance(event, FunctionCall):
            # Получаем ast_id узла function_call
            ast_id = _find_ast_id_for_event(event, "function_call", ast_analyzer)
            
            event_data.update({
                "type": "function_call",
                "ast_id": ast_id,
                "function_name": event.function_name,
                "args": _safe_json_value(event.local_vars) if event.local_vars else {},
            })
            
            if event.call_line:
                event_data["call_line"] = event.call_line
            
            events.append(event_data)
        
        elif isinstance(event, FunctionReturn):
            # Получаем ast_id узла return_statement
            ast_id = _find_ast_id_for_event(event, "function_return", ast_analyzer)
            
            event_data.update({
                "type": "function_return",
                "ast_id": ast_id,
                "function_name": event.function_name,
            })
            
            # Сохраняем return_value, включая None (для валидации)
            # При экспорте используем специальное значение для None
            if event.return_value is None:
                event_data["return_value"] = None  # Явно сохраняем None
            else:
                event_data["return_value"] = _safe_json_value(event.return_value)
            
            events.append(event_data)
    
    return {
        "scenario_name": scenario_name,
        "events": events,
        "conditions": conditions,  # Для обратной совместимости
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


def export_scenario_to_file(
    trace: RuntimeTrace,
    output_path: str | Path,
    scenario_name: str = "default",
    ast_analyzer: "ASTNodeAnalyzer | None" = None,
) -> Path:
    """Экспортирует сценарий в JSON-файл.
    
    Args:
        trace: Трасса выполнения
        output_path: Путь к выходному файлу
        scenario_name: Имя сценария
        ast_analyzer: Анализатор AST для получения ast_id (опционально)
        
    Returns:
        Path к созданному файлу
    """
    output_path = Path(output_path)
    scenario = export_scenario_from_trace(trace, scenario_name, ast_analyzer)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(scenario, f, indent=2, ensure_ascii=False)
    
    return output_path


def build_condition_sequences_from_trace(
    trace: RuntimeTrace,
) -> dict[int, list[bool]]:
    """Строит condition_sequences для TraceScenarioConfig из трассы.
    
    Группирует значения условий по ast_id в порядке их вычисления.
    
    Args:
        trace: Трасса выполнения с событиями условий
        
    Returns:
        Словарь {ast_id: [bool, bool, ...]} для использования в TraceScenarioConfig
        
    Example:
        >>> trace = execute_with_trace(code, track_conditions=True)
        >>> sequences = build_condition_sequences_from_trace(trace)
        >>> config = TraceScenarioConfig(
        ...     name="from_runtime",
        ...     condition_sequences=sequences
        ... )
    """
    sequences: dict[int, list[bool]] = {}
    
    for event in trace.condition_evaluations:
        if event.ast_id not in sequences:
            sequences[event.ast_id] = []
        sequences[event.ast_id].append(event.value)
    
    return sequences


def export_for_trace_builder(
    trace: RuntimeTrace,
    scenario_name: str = "from_runtime",
) -> dict[str, Any]:
    """Экспортирует данные для прямого использования в TraceScenarioConfig.
    
    Args:
        trace: Трасса выполнения
        scenario_name: Имя сценария
        
    Returns:
        Словарь, который можно передать в TraceScenarioConfig(**result)
    """
    return {
        "name": scenario_name,
        "condition_sequences": build_condition_sequences_from_trace(trace),
    }


def create_scenario_from_code(
    source_code: str,
    filename: str = "<script>",
    scenario_name: str = "default",
    line_to_ast_id: dict[int, int] | None = None,
    ast_analyzer: "ASTNodeAnalyzer | None" = None,
) -> dict[str, Any]:
    """Выполняет код и создаёт сценарий из результата.
    
    Удобная функция для создания сценария в один вызов.
    
    Args:
        source_code: Исходный код Python
        filename: Имя файла
        scenario_name: Имя сценария
        line_to_ast_id: Маппинг номер строки -> ast_id
        ast_analyzer: Анализатор AST для получения ast_id (опционально)
        
    Returns:
        Словарь сценария
    """
    from src.runtime.executor import execute_with_trace
    
    trace = execute_with_trace(
        source_code,
        filename=filename,
        track_conditions=True,
        line_to_ast_id=line_to_ast_id,
    )
    
    return export_scenario_from_trace(trace, scenario_name, ast_analyzer)


def create_scenario_from_file(
    filepath: str | Path,
    scenario_name: str = "default",
    line_to_ast_id: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Выполняет файл и создаёт сценарий из результата.
    
    Args:
        filepath: Путь к Python-файлу
        scenario_name: Имя сценария
        line_to_ast_id: Маппинг номер строки -> ast_id
        
    Returns:
        Словарь сценария
    """
    filepath = Path(filepath)
    source_code = filepath.read_text(encoding='utf-8')
    
    return create_scenario_from_code(
        source_code,
        filename=str(filepath.resolve()),
        scenario_name=scenario_name,
        line_to_ast_id=line_to_ast_id,
    )


def build_line_to_ast_id_for_conditions(
    ast_analyzer: "ASTNodeAnalyzer",
) -> dict[int, int]:
    """Строит маппинг номер строки -> ast_id для условных узлов.
    
    Находит все условные выражения (в if, while) в AST и создаёт
    маппинг для использования при инструментации кода.
    
    Args:
        ast_analyzer: Анализатор AST из meaning-tree
        
    Returns:
        Словарь {line_number: ast_id}
    """
    line_to_ast_id: dict[int, int] = {}
    
    for ast_id, node in ast_analyzer.nodes_cache.items():
        node_type = node.get('type', '')
        
        # Для if_statement условие находится в branches[].condition
        if node_type == 'if_statement':
            branches = node.get('branches', [])
            for branch in branches:
                if isinstance(branch, dict):
                    condition_node = branch.get('condition')
                    if condition_node and isinstance(condition_node, dict):
                        cond_id = condition_node.get('id')
                        if cond_id:
                            line = ast_analyzer.get_code_line_number_by_id(cond_id)
                            if line:
                                line_to_ast_id[line] = cond_id
        
        # Для while_statement условие в condition
        elif node_type == 'while_statement':
            condition_node = node.get('condition')
            if condition_node and isinstance(condition_node, dict):
                cond_id = condition_node.get('id')
                if cond_id:
                    line = ast_analyzer.get_code_line_number_by_id(cond_id)
                    if line:
                        line_to_ast_id[line] = cond_id
        
        # Для for_statement условие в condition (если есть)
        elif node_type == 'for_statement':
            condition_node = node.get('condition')
            if condition_node and isinstance(condition_node, dict):
                cond_id = condition_node.get('id')
                if cond_id:
                    line = ast_analyzer.get_code_line_number_by_id(cond_id)
                    if line:
                        line_to_ast_id[line] = cond_id
        
        # Тернарный оператор (conditional_expression)
        elif node_type == 'conditional_expression':
            condition_node = node.get('condition') or node.get('test')
            if condition_node and isinstance(condition_node, dict):
                cond_id = condition_node.get('id')
                if cond_id:
                    line = ast_analyzer.get_code_line_number_by_id(cond_id)
                    if line:
                        line_to_ast_id[line] = cond_id
    
    return line_to_ast_id


def create_scenario_with_ast_analyzer(
    source_code: str,
    ast_analyzer: "ASTNodeAnalyzer",
    filename: str = "<script>",
    scenario_name: str = "default",
) -> dict[str, Any]:
    """Создаёт сценарий с корректными ast_id из meaning-tree.
    
    Использует ASTNodeAnalyzer для сопоставления всех событий
    (условия, вызовы, возвраты) с их ast_id из meaning-tree AST.
    
    Args:
        source_code: Исходный код Python
        ast_analyzer: Анализатор AST из meaning-tree
        filename: Имя файла
        scenario_name: Имя сценария
        
    Returns:
        Словарь сценария с корректными ast_id для всех событий
    """
    from src.runtime.executor import execute_with_trace
    
    line_to_ast_id = build_line_to_ast_id_for_conditions(ast_analyzer)
    
    trace = execute_with_trace(
        source_code,
        filename=filename,
        track_conditions=True,
        line_to_ast_id=line_to_ast_id,
    )
    
    return export_scenario_from_trace(trace, scenario_name, ast_analyzer)
