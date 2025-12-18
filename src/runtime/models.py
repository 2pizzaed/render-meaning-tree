"""
Модели данных для трассировки времени выполнения Python-программ.

Содержит dataclass-модели для представления событий трассировки:
- RuntimeEvent: базовый класс события
- FunctionCall: вызов функции с аргументами
- FunctionReturn: возврат из функции с результатом
- PrintOutput: перехваченный вывод print
- RuntimeTrace: контейнер всех событий трассировки
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeEvent:
    """Базовый класс события трассировки.
    
    Attributes:
        line_number: Номер строки в исходном коде, где произошло событие
        order: Порядковый номер события в трассе (устанавливается автоматически)
    """
    line_number: int
    order: int = 0
    
    def describe(self) -> str:
        """Возвращает строковое описание события."""
        return f"Event at line {self.line_number}"


@dataclass
class FunctionCall(RuntimeEvent):
    """Событие вызова функции.
    
    Attributes:
        function_name: Имя вызываемой функции
        args: Позиционные аргументы (копия значений на момент вызова)
        kwargs: Именованные аргументы (копия значений на момент вызова)
        local_vars: Локальные переменные функции (имена параметров -> значения)
        call_line: Строка, откуда был произведён вызов (если известна)
    """
    function_name: str = ""
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    local_vars: dict[str, Any] = field(default_factory=dict)
    call_line: int | None = None
    
    def describe(self) -> str:
        """Возвращает строковое описание вызова функции."""
        # Форматируем аргументы как name=value
        args_str = ", ".join(f"{k}={_safe_repr(v)}" for k, v in self.local_vars.items())
        return f"CALL {self.function_name}({args_str}) [line {self.line_number}]"
    
    def __repr__(self) -> str:
        return self.describe()


@dataclass
class FunctionReturn(RuntimeEvent):
    """Событие возврата из функции.
    
    Attributes:
        function_name: Имя функции, из которой произошёл возврат
        return_value: Возвращаемое значение (копия)
    """
    function_name: str = ""
    return_value: Any = None
    
    def describe(self) -> str:
        """Возвращает строковое описание возврата из функции."""
        return f"RETURN {self.function_name} -> {_safe_repr(self.return_value)} [line {self.line_number}]"
    
    def __repr__(self) -> str:
        return self.describe()


@dataclass
class PrintOutput(RuntimeEvent):
    """Событие вывода через print.
    
    Attributes:
        text: Текст, выведенный на экран
        args: Оригинальные аргументы, переданные в print
    """
    text: str = ""
    args: tuple[Any, ...] = field(default_factory=tuple)
    
    def describe(self) -> str:
        """Возвращает строковое описание вывода print."""
        # Экранируем переносы строк для компактного отображения
        escaped_text = self.text.replace('\n', '\\n').rstrip('\\n')
        return f'PRINT: "{escaped_text}" [line {self.line_number}]'
    
    def __repr__(self) -> str:
        return self.describe()


@dataclass
class ConditionEvaluation(RuntimeEvent):
    """Событие вычисления управляющего условия (if, while, for).
    
    Attributes:
        ast_id: ID узла AST, соответствующего условию (из meaning-tree)
        value: Результат вычисления условия (True/False)
        condition_type: Тип условия ('if', 'while', 'for', 'elif')
        expression_text: Текст выражения условия (для отладки)
    """
    ast_id: int = 0
    value: bool = False
    condition_type: str = ""
    expression_text: str = ""
    
    def describe(self) -> str:
        """Возвращает строковое описание вычисления условия."""
        return f"COND [{self.condition_type}] ast_id={self.ast_id}: {self.expression_text} -> {self.value} [line {self.line_number}]"
    
    def __repr__(self) -> str:
        return self.describe()


@dataclass
class RuntimeTrace:
    """Контейнер для всех событий трассировки выполнения программы.
    
    Attributes:
        events: Список всех событий в порядке их возникновения
        source_file: Путь к исходному файлу (или имя)
        source_code: Исходный код программы
        exception: Исключение, если выполнение завершилось с ошибкой
        exception_traceback: Traceback исключения в виде строки
    """
    events: list[RuntimeEvent] = field(default_factory=list)
    source_file: str = "<script>"
    source_code: str = ""
    exception: BaseException | None = None
    exception_traceback: str | None = None
    
    def add_event(self, event: RuntimeEvent) -> None:
        """Добавляет событие в трассу, устанавливая порядковый номер."""
        event.order = len(self.events) + 1
        self.events.append(event)
    
    @property
    def function_calls(self) -> list[FunctionCall]:
        """Возвращает только события вызовов функций."""
        return [e for e in self.events if isinstance(e, FunctionCall)]
    
    @property
    def function_returns(self) -> list[FunctionReturn]:
        """Возвращает только события возвратов из функций."""
        return [e for e in self.events if isinstance(e, FunctionReturn)]
    
    @property
    def print_outputs(self) -> list[PrintOutput]:
        """Возвращает только события вывода print."""
        return [e for e in self.events if isinstance(e, PrintOutput)]
    
    @property
    def condition_evaluations(self) -> list[ConditionEvaluation]:
        """Возвращает только события вычисления условий."""
        return [e for e in self.events if isinstance(e, ConditionEvaluation)]
    
    def get_calls_for_function(self, function_name: str) -> list[FunctionCall]:
        """Возвращает все вызовы указанной функции."""
        return [e for e in self.function_calls if e.function_name == function_name]
    
    def describe(self) -> str:
        """Возвращает полное текстовое описание трассы."""
        lines = [f"=== Трасса для {self.source_file} ==="]
        
        for event in self.events:
            lines.append(f"{event.order}. {event.describe()}")
        
        if self.exception:
            lines.append(f"\n!!! Исключение: {type(self.exception).__name__}: {self.exception}")
            if self.exception_traceback:
                lines.append(self.exception_traceback)
        
        lines.append(f"\nВсего событий: {len(self.events)}")
        lines.append(f"  - Вызовов функций: {len(self.function_calls)}")
        lines.append(f"  - Возвратов: {len(self.function_returns)}")
        lines.append(f"  - Выводов print: {len(self.print_outputs)}")
        lines.append(f"  - Условий: {len(self.condition_evaluations)}")
        
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        return f"RuntimeTrace(events={len(self.events)}, file={self.source_file!r})"


def _safe_repr(value: Any, max_length: int = 50) -> str:
    """Безопасное представление значения с ограничением длины.
    
    Args:
        value: Значение для представления
        max_length: Максимальная длина строки представления
        
    Returns:
        Строковое представление значения
    """
    try:
        r = repr(value)
        if len(r) > max_length:
            return r[:max_length - 3] + "..."
        return r
    except Exception:
        return f"<{type(value).__name__}>"
