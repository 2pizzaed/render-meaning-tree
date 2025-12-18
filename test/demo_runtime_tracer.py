#!/usr/bin/env python
"""
Демонстрационный скрипт для подсистемы трассировки времени выполнения.

Запускает примеры из папки recursion_examples и выводит полную раскладку трассы
с указанием на конкретные действия и собранные значения.

Использование:
    python test/demo_runtime_tracer.py                    # Запустить все примеры
    python test/demo_runtime_tracer.py 01_sum_to_n.py     # Запустить конкретный пример
    python test/demo_runtime_tracer.py --list             # Показать список примеров
    python test/demo_runtime_tracer.py --help             # Справка
"""

import argparse
import sys
from pathlib import Path

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime import execute_file_with_trace, execute_with_trace, RuntimeTrace


# Путь к папке с примерами рекурсии
EXAMPLES_DIR = PROJECT_ROOT / "test" / "data" / "task_code" / "recursion_examples"


def list_examples() -> list[Path]:
    """Возвращает список всех Python-файлов с примерами."""
    if not EXAMPLES_DIR.exists():
        return []
    return sorted(EXAMPLES_DIR.glob("*.py"))


def print_trace_detailed(trace: RuntimeTrace, show_source: bool = False) -> None:
    """Выводит детальную информацию о трассе.
    
    Args:
        trace: Объект трассы
        show_source: Показывать ли исходный код
    """
    print("=" * 70)
    print(f"ФАЙЛ: {trace.source_file}")
    print("=" * 70)
    
    if show_source and trace.source_code:
        print("\n--- Исходный код ---")
        for i, line in enumerate(trace.source_code.splitlines(), 1):
            print(f"{i:3}| {line}")
        print("-" * 40)
    
    print(f"\n--- Трасса выполнения ({len(trace.events)} событий) ---\n")
    
    indent_level = 0
    call_stack = []
    
    for event in trace.events:
        # Формируем отступ для визуализации вложенности
        indent = "  " * indent_level
        
        if hasattr(event, 'function_name'):
            from src.runtime import FunctionCall, FunctionReturn
            
            if isinstance(event, FunctionCall):
                # Формируем строку аргументов
                args_parts = []
                for name, value in event.local_vars.items():
                    args_parts.append(f"{name}={_format_value(value)}")
                args_str = ", ".join(args_parts)
                
                print(f"{event.order:3}. {indent}--> CALL {event.function_name}({args_str})")
                print(f"     {indent}    [line {event.line_number}]")
                
                call_stack.append(event.function_name)
                indent_level += 1
                
            elif isinstance(event, FunctionReturn):
                indent_level = max(0, indent_level - 1)
                indent = "  " * indent_level
                
                print(f"{event.order:3}. {indent}<-- RETURN {event.function_name} = {_format_value(event.return_value)}")
                print(f"     {indent}    [line {event.line_number}]")
                
                if call_stack and call_stack[-1] == event.function_name:
                    call_stack.pop()
        else:
            # PrintOutput
            text = event.text.rstrip('\n')
            print(f"{event.order:3}. {indent}>>> PRINT: \"{text}\"")
            print(f"     {indent}    [line {event.line_number}]")
        
        print()
    
    # Статистика
    print("-" * 40)
    print("STATISTICS:")
    print(f"  - Total events: {len(trace.events)}")
    print(f"  - Function calls: {len(trace.function_calls)}")
    print(f"  - Returns: {len(trace.function_returns)}")
    print(f"  - Print outputs: {len(trace.print_outputs)}")
    
    # Уникальные функции
    unique_funcs = set(c.function_name for c in trace.function_calls)
    if unique_funcs:
        print(f"  - Functions called: {', '.join(sorted(unique_funcs))}")
    
    # Информация об ошибке
    if trace.exception:
        print(f"\n!!! ERROR: {type(trace.exception).__name__}: {trace.exception}")
    
    print()


def _format_value(value, max_len: int = 40) -> str:
    """Форматирует значение для вывода."""
    try:
        s = repr(value)
        if len(s) > max_len:
            s = s[:max_len - 3] + "..."
        return s
    except Exception:
        return f"<{type(value).__name__}>"


def run_example(filepath: Path, show_source: bool = False, quiet: bool = False) -> RuntimeTrace:
    """Запускает один пример и выводит трассу.
    
    Args:
        filepath: Путь к файлу примера
        show_source: Показывать исходный код
        quiet: Не выводить трассу (только выполнить)
        
    Returns:
        Объект RuntimeTrace
    """
    trace = execute_file_with_trace(filepath)
    
    if not quiet:
        print_trace_detailed(trace, show_source=show_source)
    
    return trace


def run_all_examples(show_source: bool = False, limit: int = None) -> None:
    """Запускает все примеры из папки recursion_examples.
    
    Args:
        show_source: Показывать исходный код
        limit: Ограничить количество примеров
    """
    examples = list_examples()
    
    if not examples:
        print(f"Примеры не найдены в {EXAMPLES_DIR}")
        return
    
    if limit:
        examples = examples[:limit]
    
    print(f"Найдено примеров: {len(examples)}")
    print()
    
    for i, filepath in enumerate(examples, 1):
        print(f"\n{'#' * 70}")
        print(f"# ПРИМЕР {i}/{len(examples)}: {filepath.name}")
        print(f"{'#' * 70}\n")
        
        try:
            run_example(filepath, show_source=show_source)
        except Exception as e:
            print(f"Ошибка при выполнении {filepath.name}: {e}")
        
        print("\n")


def run_inline_demo() -> None:
    """Демонстрация с инлайн-кодом."""
    print("=" * 70)
    print("ДЕМОНСТРАЦИЯ: Факториал")
    print("=" * 70)
    
    code = '''
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

result = factorial(5)
print("5! =", result)
'''
    
    print("\n--- Код ---")
    print(code)
    
    trace = execute_with_trace(code, filename="factorial_demo.py")
    print_trace_detailed(trace)
    
    print("\n" + "=" * 70)
    print("ДЕМОНСТРАЦИЯ: Числа Фибоначчи")
    print("=" * 70)
    
    code = '''
def fib(n):
    if n <= 2:
        return n
    return fib(n - 1) + fib(n - 2)

print("fib(5) =", fib(5))
'''
    
    print("\n--- Код ---")
    print(code)
    
    trace = execute_with_trace(code, filename="fibonacci_demo.py")
    print_trace_detailed(trace)


def main():
    parser = argparse.ArgumentParser(
        description="Демонстрация трассировки выполнения Python-программ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s                          Запустить встроенную демонстрацию
  %(prog)s --all                    Запустить все примеры из recursion_examples
  %(prog)s --all --limit 5          Запустить первые 5 примеров
  %(prog)s 01_sum_to_n.py           Запустить конкретный пример
  %(prog)s --list                   Показать список доступных примеров
  %(prog)s --source 03_gcd.py       Показать код и трассу примера
"""
    )
    
    parser.add_argument(
        'example',
        nargs='?',
        help='Имя файла примера для запуска (например: 01_sum_to_n.py)'
    )
    
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Запустить все примеры из recursion_examples'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='Показать список доступных примеров'
    )
    
    parser.add_argument(
        '--source', '-s',
        action='store_true',
        help='Показывать исходный код примеров'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Ограничить количество примеров при --all'
    )
    
    args = parser.parse_args()
    
    # Показать список примеров
    if args.list:
        examples = list_examples()
        if examples:
            print(f"Доступные примеры в {EXAMPLES_DIR}:\n")
            for ex in examples:
                print(f"  • {ex.name}")
            print(f"\nВсего: {len(examples)} примеров")
        else:
            print(f"Примеры не найдены в {EXAMPLES_DIR}")
        return
    
    # Запустить все примеры
    if args.all:
        run_all_examples(show_source=args.source, limit=args.limit)
        return
    
    # Запустить конкретный пример
    if args.example:
        # Ищем файл по имени
        filepath = EXAMPLES_DIR / args.example
        if not filepath.exists():
            # Попробуем найти в других местах
            alt_path = PROJECT_ROOT / "test" / "data" / "task_code" / args.example
            if alt_path.exists():
                filepath = alt_path
            else:
                print(f"Файл не найден: {args.example}")
                print(f"Проверьте путь или используйте --list для списка примеров")
                sys.exit(1)
        
        run_example(filepath, show_source=args.source)
        return
    
    # По умолчанию — встроенная демонстрация
    run_inline_demo()


if __name__ == '__main__':
    main()
