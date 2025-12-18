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


class ConditionInstrumenter(ast.NodeTransformer):
    """AST-трансформер для инструментации условий.
    
    Оборачивает условные выражения в if, while, for вызовом
    __trace_condition__ для захвата их значений.
    
    Attributes:
        source_lines: Строки исходного кода для извлечения текста условий
        line_to_ast_id: Маппинг номер строки -> ast_id из meaning-tree
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
    
    def _get_expr_text(self, node: ast.expr) -> str:
        """Извлекает текст выражения из исходного кода."""
        try:
            return ast.unparse(node)
        except Exception:
            # Fallback для старых версий Python
            if hasattr(node, 'lineno') and node.lineno <= len(self.source_lines):
                return self.source_lines[node.lineno - 1].strip()
            return "<expr>"
    
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
        ast_id = self.line_to_ast_id.get(line_no, 0)
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
        """For-циклы не имеют условия для инструментации."""
        # For в Python итерирует по коллекции, нет явного условия
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
