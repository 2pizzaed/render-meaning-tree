"""
AST-инструментатор для захвата значений условий при выполнении.

Модифицирует Python AST, оборачивая условные выражения (if, while, for)
вызовом функции __trace_condition__, которая записывает значение условия
и возвращает его для дальнейшего использования.

Пример трансформации:
    До:   if x > 0:
    После: if __trace_condition__(42, 3, 'if', 'x > 0', x > 0):

Где:
    - 42 - ast_id из meaning-tree AST (или 0 если неизвестен)
    - 3 - номер строки
    - 'if' - тип условия
    - 'x > 0' - текст выражения
    - x > 0 - само выражение (вычисляется последним)
"""

import ast
from typing import Any

from src.runtime.models import ConditionEvaluation


# Глобальный список для сбора событий условий
_condition_events: list[ConditionEvaluation] = []


def _trace_condition_impl(ast_id: int, line_no: int, cond_type: str, expr_text: str, value: Any) -> bool:
    """Функция-трекер для записи значений условий.
    
    Вызывается из инструментированного кода для каждого условия.
    
    Args:
        ast_id: ID узла AST из meaning-tree (или 0)
        line_no: Номер строки в исходном коде
        cond_type: Тип условия ('if', 'while', 'for', 'elif')
        expr_text: Текст выражения условия
        value: Вычисленное значение условия
        
    Returns:
        bool(value) для использования в управляющей конструкции
    """
    bool_value = bool(value)
    event = ConditionEvaluation(
        line_number=line_no,
        ast_id=ast_id,
        value=bool_value,
        condition_type=cond_type,
        expression_text=expr_text,
    )
    _condition_events.append(event)
    return bool_value


def get_condition_events() -> list[ConditionEvaluation]:
    """Возвращает собранные события условий."""
    return _condition_events.copy()


def clear_condition_events() -> None:
    """Очищает список событий условий."""
    _condition_events.clear()


def _get_container_length(container: Any) -> int | None:
    """Определяет длину контейнера через преобразование в список.
    
    Args:
        container: Итерируемый объект
        
    Returns:
        Длина контейнера или None, если > 100 элементов или ошибка
    """
    try:
        lst = list(container)
        if len(lst) > 100:
            return None  # Бесконечный или слишком большой
        return len(lst)
    except (TypeError, MemoryError):
        return None


def _trace_for_iter_impl(ast_id: int, line_no: int, cond_type: str, expr_text: str, iterator: Any) -> Any:
    """Обёртка итератора для генерации событий условий в циклах for.
    
    Args:
        ast_id: ID узла AST цикла
        line_no: Номер строки
        cond_type: Тип цикла ('for_each' или 'range_for')
        expr_text: Текст выражения
        iterator: Итерируемый объект
        
    Returns:
        Обёрнутый итератор, который генерирует события
    """
    class TracedIterator:
        def __init__(self, inner_iter, ast_id, line_no, cond_type, expr_text):
            self.inner_iter = iter(inner_iter)
            self.ast_id = ast_id
            self.line_no = line_no
            self.cond_type = cond_type
            self.expr_text = expr_text
            
        def __iter__(self):
            return self
            
        def __next__(self):
            try:
                value = next(self.inner_iter)
                # Генерируем событие условия True при получении элемента
                _trace_condition_impl(self.ast_id, self.line_no, self.cond_type, self.expr_text, True)
                return value
            except StopIteration:
                # Генерируем событие условия False при окончании
                _trace_condition_impl(self.ast_id, self.line_no, self.cond_type, self.expr_text, False)
                raise
    
    return TracedIterator(iterator, ast_id, line_no, cond_type, expr_text)


class ConditionInstrumenter(ast.NodeTransformer):
    """AST-трансформер для инструментации условий.
    
    Оборачивает условные выражения в if, while, for вызовом
    __trace_condition__ для захвата их значений.
    
    Attributes:
        source_lines: Строки исходного кода для извлечения текста условий
        line_to_ast_id: Маппинг номер строки -> ast_id из meaning-tree
        ast_id_list: Отсортированный список (line, ast_id) для поиска ближайшего
    """
    
    def __init__(
        self,
        source_code: str,
        line_to_ast_id: dict[int, int] | None = None,
    ):
        """Инициализирует инструментатор.
        
        Args:
            source_code: Исходный код программы
            line_to_ast_id: Маппинг номер строки -> ast_id (опционально)
        """
        self.source_lines = source_code.splitlines()
        self.line_to_ast_id = line_to_ast_id or {}
        
        # Создаём очередь ast_id, отсортированную по номеру строки
        # meaning-tree трансформирует код (удаляет пустые строки, декораторы),
        # поэтому номера строк не совпадают.
        # Используем очередь: каждое условие берёт следующий ast_id по порядку
        self._ast_id_queue = [ast_id for _, ast_id in sorted(self.line_to_ast_id.items())]
        self._ast_id_index = 0
    
    def _get_expr_text(self, node: ast.expr) -> str:
        """Извлекает текст выражения из исходного кода."""
        try:
            return ast.unparse(node)
        except Exception:
            # Fallback для старых версий Python
            if hasattr(node, 'lineno') and node.lineno <= len(self.source_lines):
                return self.source_lines[node.lineno - 1].strip()
            return "<expr>"
    
    def _get_next_ast_id(self) -> int:
        """Возвращает следующий ast_id из очереди.
        
        meaning-tree трансформирует код (удаляет пустые строки, декораторы),
        поэтому номера строк не совпадают. Используем очередь: каждое
        условие берёт следующий ast_id по порядку появления в коде.
        
        Returns:
            ast_id или 0, если очередь исчерпана
        """
        if self._ast_id_index < len(self._ast_id_queue):
            ast_id = self._ast_id_queue[self._ast_id_index]
            self._ast_id_index += 1
            return ast_id
        return 0
    
    def _wrap_condition(
        self,
        test_node: ast.expr,
        cond_type: str,
    ) -> ast.Call:
        """Оборачивает условное выражение в вызов __trace_condition__.
        
        Args:
            test_node: AST-узел условного выражения
            cond_type: Тип условия ('if', 'while', 'for', 'elif')
            
        Returns:
            AST-узел вызова __trace_condition__
        """
        line_no = getattr(test_node, 'lineno', 0)
        ast_id = self._get_next_ast_id()
        expr_text = self._get_expr_text(test_node)
        
        # Создаём вызов: __trace_condition__(ast_id, line_no, cond_type, expr_text, <expr>)
        call = ast.Call(
            func=ast.Name(id='__trace_condition__', ctx=ast.Load()),
            args=[
                ast.Constant(value=ast_id),
                ast.Constant(value=line_no),
                ast.Constant(value=cond_type),
                ast.Constant(value=expr_text),
                test_node,  # Само выражение вычисляется последним
            ],
            keywords=[],
        )
        
        # Копируем информацию о позиции
        ast.copy_location(call, test_node)
        return call
    
    def visit_If(self, node: ast.If) -> ast.If:
        """Инструментирует условие if/elif."""
        # Определяем тип условия
        # Примечание: elif в Python AST представлен как вложенный If в orelse
        cond_type = 'if'
        
        # Оборачиваем условие
        node.test = self._wrap_condition(node.test, cond_type)
        
        # Рекурсивно обрабатываем вложенные узлы
        self.generic_visit(node)
        return node
    
    def visit_While(self, node: ast.While) -> ast.While:
        """Инструментирует условие while."""
        node.test = self._wrap_condition(node.test, 'while')
        self.generic_visit(node)
        return node
    
    def visit_For(self, node: ast.For) -> ast.For:
        """Инструментирует циклы for для захвата событий условий.
        
        Оборачивает итератор в функцию __trace_for_iter__, которая
        генерирует события условия при получении элемента (True) и окончании (False).
        """
        line_no = getattr(node, 'lineno', 0)
        ast_id = self._get_next_ast_id()
        
        # Сохраняем оригинальный итератор для получения текста
        original_iter = node.iter
        
        # Определяем тип цикла (for_each или range_for)
        # Проверяем, является ли iter вызовом range()
        is_range = (
            isinstance(original_iter, ast.Call) and
            isinstance(original_iter.func, ast.Name) and
            original_iter.func.id == 'range'
        )
        cond_type = 'range_for' if is_range else 'for_each'
        
        # Получаем текст выражения из исходного кода
        expr_text = self._get_expr_text(original_iter)
        
        # Оборачиваем итератор в вызов __trace_for_iter__
        node.iter = ast.Call(
            func=ast.Name(id='__trace_for_iter__', ctx=ast.Load()),
            args=[
                ast.Constant(value=ast_id),
                ast.Constant(value=line_no),
                ast.Constant(value=cond_type),
                ast.Constant(value=expr_text),
                original_iter,  # Оригинальный итератор
            ],
            keywords=[]
        )
        ast.copy_location(node.iter, node)
        
        # Рекурсивно обрабатываем вложенные узлы
        self.generic_visit(node)
        return node
    
    def visit_comprehension(self, node: ast.comprehension) -> ast.comprehension:
        """Инструментирует условия в list/dict/set comprehensions."""
        # Оборачиваем все if-условия в comprehension
        node.ifs = [
            self._wrap_condition(if_clause, 'comprehension_if')
            for if_clause in node.ifs
        ]
        self.generic_visit(node)
        return node
    
    def visit_IfExp(self, node: ast.IfExp) -> ast.IfExp:
        """Инструментирует тернарный оператор (x if cond else y)."""
        node.test = self._wrap_condition(node.test, 'ternary')
        self.generic_visit(node)
        return node


def instrument_code(
    source_code: str,
    line_to_ast_id: dict[int, int] | None = None,
) -> str:
    """Инструментирует исходный код для захвата значений условий.
    
    Args:
        source_code: Исходный код Python
        line_to_ast_id: Маппинг номер строки -> ast_id (опционально)
        
    Returns:
        Инструментированный код с обёрнутыми условиями
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        # Если код не парсится, возвращаем как есть
        return source_code
    
    instrumenter = ConditionInstrumenter(source_code, line_to_ast_id)
    instrumented_tree = instrumenter.visit(tree)
    ast.fix_missing_locations(instrumented_tree)
    
    return ast.unparse(instrumented_tree)


def create_execution_globals() -> dict[str, Any]:
    """Создаёт глобальное пространство имён для выполнения инструментированного кода.
    
    Returns:
        Словарь с глобальными переменными, включая __trace_condition__
    """
    return {
        '__trace_condition__': _trace_condition_impl,
        '__builtins__': __builtins__,
    }
