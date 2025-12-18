"""
Трассировщик выполнения Python-кода на базе sys.settrace.

Перехватывает:
- Вызовы функций (с аргументами)
- Возвраты из функций (с возвращаемыми значениями)
- Вывод через print

Фильтрует события, отслеживая только функции из указанного файла.
"""

import builtins
import copy
import sys
from io import StringIO
from types import FrameType
from typing import Any, Callable

from src.runtime.models import (
    FunctionCall,
    FunctionReturn,
    PrintOutput,
    RuntimeTrace,
)


class RuntimeTracer:
    """Трассировщик выполнения Python-кода.
    
    Использует sys.settrace для перехвата вызовов функций и возвратов.
    Подменяет builtins.print для захвата вывода.
    
    Attributes:
        trace: Объект RuntimeTrace, в который собираются события
        target_filename: Имя файла, для которого отслеживаются функции
        _original_print: Сохранённая оригинальная функция print
        _call_stack: Стек вызовов для отслеживания вложенности
        _active: Флаг активности трассировщика
    """
    
    def __init__(self, target_filename: str = "<script>"):
        """Инициализирует трассировщик.
        
        Args:
            target_filename: Имя файла, функции которого нужно отслеживать
        """
        self.trace = RuntimeTrace(source_file=target_filename)
        self.target_filename = target_filename
        self._original_print: Callable | None = None
        self._call_stack: list[str] = []
        self._active = False
        self._current_line: int = 0
    
    def start(self) -> None:
        """Запускает трассировку."""
        if self._active:
            return
        
        self._active = True
        self._original_print = builtins.print
        builtins.print = self._traced_print
        sys.settrace(self._trace_function)
    
    def stop(self) -> None:
        """Останавливает трассировку."""
        if not self._active:
            return
        
        self._active = False
        sys.settrace(None)
        
        if self._original_print is not None:
            builtins.print = self._original_print
            self._original_print = None
    
    def _is_target_file(self, frame: FrameType) -> bool:
        """Проверяет, принадлежит ли фрейм целевому файлу.
        
        Args:
            frame: Фрейм выполнения
            
        Returns:
            True, если фрейм из целевого файла
        """
        filename = frame.f_code.co_filename
        # Сравниваем с целевым файлом
        return filename == self.target_filename
    
    def _trace_function(self, frame: FrameType, event: str, arg: Any) -> Callable | None:
        """Функция трассировки для sys.settrace.
        
        Args:
            frame: Текущий фрейм выполнения
            event: Тип события ('call', 'return', 'line', 'exception')
            arg: Дополнительный аргумент (зависит от события)
            
        Returns:
            Функция для локальной трассировки или None
        """
        if not self._active:
            return None
        
        # Обновляем текущую строку для print
        if event == 'line':
            self._current_line = frame.f_lineno
            return self._trace_function
        
        # Проверяем, что это целевой файл
        if not self._is_target_file(frame):
            return None
        
        if event == 'call':
            self._handle_call(frame)
            return self._trace_function
        
        elif event == 'return':
            self._handle_return(frame, arg)
            return None
        
        return self._trace_function
    
    def _handle_call(self, frame: FrameType) -> None:
        """Обрабатывает событие вызова функции.
        
        Args:
            frame: Фрейм вызываемой функции
        """
        func_name = frame.f_code.co_name
        
        # Пропускаем служебные функции и модуль верхнего уровня
        if func_name == '<module>':
            return
        
        # Получаем номер строки определения функции
        line_number = frame.f_lineno
        
        # Получаем строку вызова из родительского фрейма
        call_line = None
        if frame.f_back:
            call_line = frame.f_back.f_lineno
        
        # Извлекаем аргументы функции из f_locals
        # f_locals содержит локальные переменные, включая параметры функции
        local_vars = self._copy_locals(frame)
        
        # Фильтруем только параметры функции (по co_varnames)
        code = frame.f_code
        param_count = code.co_argcount + code.co_kwonlyargcount
        if code.co_flags & 0x04:  # *args
            param_count += 1
        if code.co_flags & 0x08:  # **kwargs
            param_count += 1
        
        param_names = code.co_varnames[:param_count]
        func_params = {name: local_vars.get(name) for name in param_names if name in local_vars}
        
        event = FunctionCall(
            line_number=line_number,
            function_name=func_name,
            local_vars=func_params,
            call_line=call_line,
        )
        
        self.trace.add_event(event)
        self._call_stack.append(func_name)
    
    def _handle_return(self, frame: FrameType, return_value: Any) -> None:
        """Обрабатывает событие возврата из функции.
        
        Args:
            frame: Фрейм функции
            return_value: Возвращаемое значение
        """
        func_name = frame.f_code.co_name
        
        # Пропускаем модуль верхнего уровня
        if func_name == '<module>':
            return
        
        line_number = frame.f_lineno
        
        # Копируем возвращаемое значение
        try:
            copied_value = copy.deepcopy(return_value)
        except Exception:
            copied_value = return_value
        
        event = FunctionReturn(
            line_number=line_number,
            function_name=func_name,
            return_value=copied_value,
        )
        
        self.trace.add_event(event)
        
        if self._call_stack and self._call_stack[-1] == func_name:
            self._call_stack.pop()
    
    def _traced_print(self, *args, **kwargs) -> None:
        """Подменённая функция print для захвата вывода.
        
        Args:
            *args: Аргументы для print
            **kwargs: Именованные аргументы для print
        """
        # Собираем текст, который будет выведен
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        
        # Форматируем вывод как это делает print
        text_parts = [str(arg) for arg in args]
        text = sep.join(text_parts) + end
        
        # Получаем номер строки
        # Используем текущий фрейм для определения строки вызова print
        frame = sys._getframe(1)
        line_number = frame.f_lineno if frame else self._current_line
        
        # Проверяем, что print вызван из целевого файла
        if frame and self._is_target_file(frame):
            # Копируем аргументы
            try:
                args_copy = tuple(copy.deepcopy(arg) for arg in args)
            except Exception:
                args_copy = args
            
            event = PrintOutput(
                line_number=line_number,
                text=text,
                args=args_copy,
            )
            self.trace.add_event(event)
        
        # Вызываем оригинальный print
        if self._original_print:
            self._original_print(*args, **kwargs)
    
    def _copy_locals(self, frame: FrameType) -> dict[str, Any]:
        """Копирует локальные переменные фрейма.
        
        Args:
            frame: Фрейм выполнения
            
        Returns:
            Словарь с копиями локальных переменных
        """
        result = {}
        for name, value in frame.f_locals.items():
            try:
                result[name] = copy.deepcopy(value)
            except Exception:
                # Если не удаётся скопировать, сохраняем строковое представление
                try:
                    result[name] = repr(value)
                except Exception:
                    result[name] = f"<{type(value).__name__}>"
        return result
    
    def __enter__(self) -> 'RuntimeTracer':
        """Контекстный менеджер: вход."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Контекстный менеджер: выход."""
        self.stop()
        return False  # Не подавляем исключения
