"""
Исполнитель Python-кода с трассировкой.

Предоставляет функции для выполнения Python-кода с автоматическим
сбором информации о вызовах функций, возвратах и выводе print.
"""

import traceback
from pathlib import Path
from typing import Any

from src.runtime.models import RuntimeTrace
from src.runtime.tracer import RuntimeTracer


def execute_with_trace(
    source_code: str,
    filename: str = "<script>",
    globals_dict: dict[str, Any] | None = None,
    locals_dict: dict[str, Any] | None = None,
    track_conditions: bool = False,
    line_to_ast_id: dict[int, int] | None = None,
) -> RuntimeTrace:
    """Выполняет Python-код и возвращает трассу выполнения.
    
    Args:
        source_code: Исходный код Python для выполнения
        filename: Имя файла для отображения в трассировке
        globals_dict: Глобальное пространство имён (если None, создаётся новое)
        locals_dict: Локальное пространство имён (если None, используется globals_dict)
        track_conditions: Если True, инструментирует код для захвата значений условий
        line_to_ast_id: Маппинг номер строки -> ast_id для связи с meaning-tree AST
        
    Returns:
        RuntimeTrace с собранными событиями выполнения
        
    Example:
        >>> code = '''
        ... def factorial(n):
        ...     if n <= 1:
        ...         return 1
        ...     return n * factorial(n - 1)
        ... 
        ... result = factorial(5)
        ... print("Result:", result)
        ... '''
        >>> trace = execute_with_trace(code, track_conditions=True)
        >>> print(trace.describe())
    """
    # Инструментируем код для захвата условий, если нужно
    code_to_execute = source_code
    condition_tracker_func = None
    
    if track_conditions:
        from src.runtime.instrumenter import (
            instrument_code,
            clear_condition_events,
            get_condition_events,
            _trace_condition_impl,
        )
        clear_condition_events()
        code_to_execute = instrument_code(source_code, line_to_ast_id)
        condition_tracker_func = _trace_condition_impl
    
    # Подготавливаем пространства имён
    if globals_dict is None:
        globals_dict = {
            '__name__': '__main__',
            '__file__': filename,
            '__builtins__': __builtins__,
        }
    
    # Создаём трассировщик (нужен для передачи в condition_tracker)
    tracer = RuntimeTracer(target_filename=filename)
    tracer.trace.source_code = source_code  # Сохраняем оригинальный код
    
    # Создаём обёртку для condition_tracker с привязкой к trace
    if condition_tracker_func is not None:
        def trace_condition_wrapper(ast_id, line_no, cond_type, expr_text, value):
            return condition_tracker_func(ast_id, line_no, cond_type, expr_text, value, tracer.trace)
        globals_dict['__trace_condition__'] = trace_condition_wrapper
    
    if locals_dict is None:
        locals_dict = globals_dict
    
    # Компилируем код
    try:
        compiled_code = compile(code_to_execute, filename, 'exec')
    except SyntaxError as e:
        trace = RuntimeTrace(source_file=filename, source_code=source_code)
        trace.exception = e
        trace.exception_traceback = traceback.format_exc()
        return trace
    
    # Выполняем код с трассировкой
    try:
        tracer.start()
        exec(compiled_code, globals_dict, locals_dict)
    except Exception as e:
        tracer.trace.exception = e
        tracer.trace.exception_traceback = traceback.format_exc()
    finally:
        tracer.stop()
    
    # Если события условий не были добавлены через trace (fallback),
    # добавляем их сейчас (для обратной совместимости)
    if track_conditions:
        condition_events = get_condition_events()
        if condition_events:
            # События не были добавлены через trace, добавляем сейчас
            for event in condition_events:
                tracer.trace.add_event(event)
            clear_condition_events()
    
    return tracer.trace


def execute_file_with_trace(
    filepath: str | Path,
    globals_dict: dict[str, Any] | None = None,
    locals_dict: dict[str, Any] | None = None,
) -> RuntimeTrace:
    """Выполняет Python-файл и возвращает трассу выполнения.
    
    Args:
        filepath: Путь к Python-файлу
        globals_dict: Глобальное пространство имён
        locals_dict: Локальное пространство имён
        
    Returns:
        RuntimeTrace с собранными событиями выполнения
        
    Raises:
        FileNotFoundError: Если файл не найден
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"Файл не найден: {filepath}")
    
    source_code = filepath.read_text(encoding='utf-8')
    filename = str(filepath.resolve())
    
    return execute_with_trace(
        source_code=source_code,
        filename=filename,
        globals_dict=globals_dict,
        locals_dict=locals_dict,
    )


def execute_and_print_trace(
    source_code: str,
    filename: str = "<script>",
    verbose: bool = True,
) -> RuntimeTrace:
    """Выполняет код, печатает трассу и возвращает её.
    
    Удобная функция для быстрого тестирования и демонстрации.
    
    Args:
        source_code: Исходный код Python
        filename: Имя файла
        verbose: Если True, печатает подробную трассу
        
    Returns:
        RuntimeTrace с собранными событиями
    """
    trace = execute_with_trace(source_code, filename)
    
    if verbose:
        print(trace.describe())
    
    return trace


def trace_function_calls(
    source_code: str,
    function_name: str | None = None,
    filename: str = "<script>",
) -> list[dict[str, Any]]:
    """Выполняет код и возвращает информацию о вызовах функций.
    
    Упрощённый интерфейс для получения только вызовов функций.
    
    Args:
        source_code: Исходный код Python
        function_name: Если указано, фильтрует вызовы только этой функции
        filename: Имя файла
        
    Returns:
        Список словарей с информацией о вызовах:
        [{'name': str, 'args': dict, 'line': int, 'order': int}, ...]
    """
    trace = execute_with_trace(source_code, filename)
    
    calls = trace.function_calls
    if function_name:
        calls = [c for c in calls if c.function_name == function_name]
    
    return [
        {
            'name': call.function_name,
            'args': call.local_vars,
            'line': call.line_number,
            'order': call.order,
        }
        for call in calls
    ]
