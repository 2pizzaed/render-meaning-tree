"""
Экспорт результатов runtime трассировки в формат сценариев.

Создаёт JSON-файлы сценариев, совместимые с TraceScenarioConfig,
на основе реального выполнения программы.

Формат сценария:
{
    "scenario_name": "default",
    "conditions": [
        {
            "ast_id": 16,
            "condition_value": "true",
            "position_in_trace": 5,
            "line_number": 3,
            "expression_text": "x > 0"
        },
        ...
    ]
}
"""

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.runtime.models import ConditionEvaluation, RuntimeTrace

if TYPE_CHECKING:
    from src.ast_analyzer import ASTNodeAnalyzer


def export_scenario_from_trace(
    trace: RuntimeTrace,
    scenario_name: str = "default",
) -> dict[str, Any]:
    """Создаёт сценарий из трассы выполнения.
    
    Args:
        trace: Трасса выполнения с событиями условий
        scenario_name: Имя сценария
        
    Returns:
        Словарь сценария для сериализации в JSON
    """
    conditions = []
    
    for event in trace.condition_evaluations:
        condition_data = {
            "ast_id": event.ast_id,
            "condition_value": "true" if event.value else "false",
            "line_number": event.line_number,
        }
        
        # Добавляем опциональные поля
        if event.expression_text:
            condition_data["expression_text"] = event.expression_text
        if event.condition_type:
            condition_data["condition_type"] = event.condition_type
        if event.order:
            condition_data["order"] = event.order
            
        conditions.append(condition_data)
    
    return {
        "scenario_name": scenario_name,
        "conditions": conditions,
    }


def export_scenario_to_file(
    trace: RuntimeTrace,
    output_path: str | Path,
    scenario_name: str = "default",
) -> Path:
    """Экспортирует сценарий в JSON-файл.
    
    Args:
        trace: Трасса выполнения
        output_path: Путь к выходному файлу
        scenario_name: Имя сценария
        
    Returns:
        Path к созданному файлу
    """
    output_path = Path(output_path)
    scenario = export_scenario_from_trace(trace, scenario_name)
    
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
) -> dict[str, Any]:
    """Выполняет код и создаёт сценарий из результата.
    
    Удобная функция для создания сценария в один вызов.
    
    Args:
        source_code: Исходный код Python
        filename: Имя файла
        scenario_name: Имя сценария
        line_to_ast_id: Маппинг номер строки -> ast_id
        
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
    
    return export_scenario_from_trace(trace, scenario_name)


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
    
    # Типы узлов, которые являются условными конструкциями
    condition_parent_types = {
        'if_statement', 'while_statement', 'for_statement',
        'conditional_expression',  # тернарный оператор
    }
    
    for ast_id, node in ast_analyzer.nodes_cache.items():
        node_type = node.get('type', '')
        
        # Для if/while/for нужно найти условие внутри
        if node_type in condition_parent_types:
            # Ищем условие (обычно в поле 'condition' или 'test')
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
    
    Использует ASTNodeAnalyzer для сопоставления условий
    с их ast_id из meaning-tree AST.
    
    Args:
        source_code: Исходный код Python
        ast_analyzer: Анализатор AST из meaning-tree
        filename: Имя файла
        scenario_name: Имя сценария
        
    Returns:
        Словарь сценария с корректными ast_id
    """
    line_to_ast_id = build_line_to_ast_id_for_conditions(ast_analyzer)
    
    return create_scenario_from_code(
        source_code,
        filename=filename,
        scenario_name=scenario_name,
        line_to_ast_id=line_to_ast_id,
    )
