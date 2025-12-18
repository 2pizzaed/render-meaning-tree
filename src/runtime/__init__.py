"""
Подсистема трассировки времени выполнения Python-программ.

Позволяет выполнять Python-код с автоматическим сбором информации:
- Вызовы функций (с фактическими параметрами)
- Возвраты из функций (с возвращаемыми значениями)
- Вывод через print

Пример использования:
    >>> from src.runtime import execute_with_trace
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
    >>> trace = execute_with_trace(code)
    >>> print(trace.describe())
    === Трасса для <script> ===
    1. CALL factorial(n=5) [line 2]
    2. CALL factorial(n=4) [line 5]
    ...
"""

# Модели данных
from src.runtime.models import (
    RuntimeEvent,
    FunctionCall,
    FunctionReturn,
    PrintOutput,
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

__all__ = [
    # Модели
    'RuntimeEvent',
    'FunctionCall',
    'FunctionReturn',
    'PrintOutput',
    'RuntimeTrace',
    # Трассировщик
    'RuntimeTracer',
    # Функции исполнения
    'execute_with_trace',
    'execute_file_with_trace',
    'execute_and_print_trace',
    'trace_function_calls',
]
