"""
Подсистема трассировки времени выполнения Python-программ.

Позволяет выполнять Python-код с автоматическим сбором информации:
- Вызовы функций (с фактическими параметрами)
- Возвраты из функций (с возвращаемыми значениями)
- Вывод через print
- Значения условий (if, while) при track_conditions=True

Пример использования:
    >>> from src.runtime import execute_with_trace, create_scenario_from_code
    >>> 
    >>> code = '''
    ... def factorial(n):
    ...     if n <= 1:
    ...         return 1
    ...     return n * factorial(n - 1)
    ... 
    ... print("5! =", factorial(5))
    ... '''
    >>> 
    >>> # Базовая трассировка
    >>> trace = execute_with_trace(code)
    >>> print(trace.describe())
    
    >>> # С захватом условий
    >>> trace = execute_with_trace(code, track_conditions=True)
    >>> print(f"Условий: {len(trace.condition_evaluations)}")
    
    >>> # Экспорт сценария
    >>> scenario = create_scenario_from_code(code)
    >>> print(scenario)
"""

# Модели данных
from src.runtime.models import (
    RuntimeEvent,
    FunctionCall,
    FunctionReturn,
    PrintOutput,
    ConditionEvaluation,
    RuntimeTrace,
)

# Трассировщик
from src.runtime.tracer import RuntimeTracer

# Функции исполнения
from src.runtime.executor import (
    execute_with_trace,
    execute_file_with_trace,
    execute_and_print_trace,
    trace_function_calls,
)

# Функции сопоставления с TraceAct
from src.runtime.matcher import (
    enrich_trace_with_runtime,
    enrich_trace_from_scenario,
    enrich_single_scenario,
)

# Инструментация кода
from src.runtime.instrumenter import (
    instrument_code,
    ConditionInstrumenter,
)

# Экспорт сценариев
from src.runtime.scenario_exporter import (
    export_scenario_from_trace,
    export_scenario_to_file,
    build_condition_sequences_from_trace,
    export_for_trace_builder,
    create_scenario_from_code,
    create_scenario_from_file,
    build_line_to_ast_id_for_conditions,
    create_scenario_with_ast_analyzer,
)

__all__ = [
    # Модели
    'RuntimeEvent',
    'FunctionCall',
    'FunctionReturn',
    'PrintOutput',
    'ConditionEvaluation',
    'RuntimeTrace',
    # Трассировщик
    'RuntimeTracer',
    # Функции исполнения
    'execute_with_trace',
    'execute_file_with_trace',
    'execute_and_print_trace',
    'trace_function_calls',
    # Функции сопоставления
    'enrich_trace_with_runtime',
    'enrich_trace_from_scenario',
    'enrich_single_scenario',
    # Инструментация
    'instrument_code',
    'ConditionInstrumenter',
    # Экспорт сценариев
    'export_scenario_from_trace',
    'export_scenario_to_file',
    'build_condition_sequences_from_trace',
    'export_for_trace_builder',
    'create_scenario_from_code',
    'create_scenario_from_file',
    'build_line_to_ast_id_for_conditions',
    'create_scenario_with_ast_analyzer',
]
