"""
Классы для связываемых событий runtime трассировки.

Предоставляет обёртки для RuntimeEvent, которые могут быть привязаны к актам трассы.
Используется для последовательного связывания событий с актами трассы с валидацией.
"""

from typing import TYPE_CHECKING

from src.runtime.models import (
    ConditionEvaluation,
    FunctionCall,
    FunctionReturn,
    RuntimeEvent,
)

if TYPE_CHECKING:
    from src.cfg.cfg import TraceAct


class BindableEvent:
    """Базовый класс для связываемых событий.
    
    Обёртка вокруг RuntimeEvent, которая отслеживает использование события
    и предоставляет метод для проверки соответствия акту трассы.
    
    Attributes:
        event: Событие runtime трассировки
        used: Флаг использования события (True если уже привязано к акту)
    """
    
    def __init__(self, event: RuntimeEvent):
        """Инициализирует связываемое событие.
        
        Args:
            event: Событие runtime трассировки
        """
        self.event = event
        self.used = False
    
    def mark_used(self) -> None:
        """Помечает событие как использованное."""
        self.used = True
    
    def matches(self, act: "TraceAct") -> bool:
        """Проверяет, соответствует ли событие акту трассы.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если событие соответствует акту, False иначе
        """
        raise NotImplementedError("Subclasses must implement matches()")
    
    def matches_node_kind(self, act: "TraceAct") -> bool:
        """Проверяет, соответствует ли тип события типу узла акта.
        
        Проверяет только соответствие типа события (call/return/condition) типу узла (BEGIN/END/ATOM),
        без проверки деталей AST (имя функции, ast_id).
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если тип события соответствует типу узла, False иначе
        """
        raise NotImplementedError("Subclasses must implement matches_node_kind()")
    
    def matches_ast_details(self, act: "TraceAct") -> bool:
        """Проверяет соответствие деталей AST (имя функции, ast_id).
        
        Проверяет соответствие имени функции или ast_id между событием и актом.
        Используется для мягкой валидации - если не соответствует, выводится warning.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если детали AST соответствуют, False иначе
        """
        raise NotImplementedError("Subclasses must implement matches_ast_details()")
    
    def validate_match(self, act: "TraceAct") -> None:
        """Валидирует соответствие события акту, выбрасывая исключение при несоответствии.
        
        Args:
            act: Акт трассы для валидации
            
        Raises:
            ValueError: Если событие не соответствует акту
        """
        if not self.matches(act):
            raise ValueError(
                f"Event {self.event.describe()} does not match act "
                f"(node_kind={act.cfg_node.kind.value if act.cfg_node else None})"
            )


class BindableFunctionCall(BindableEvent):
    """Связываемое событие вызова функции.
    
    Соответствует BEGIN-актам функций.
    """
    
    def __init__(self, event: FunctionCall):
        """Инициализирует связываемое событие вызова функции.
        
        Args:
            event: Событие вызова функции
        """
        if not isinstance(event, FunctionCall):
            raise TypeError(f"Expected FunctionCall, got {type(event)}")
        super().__init__(event)
        self.function_call = event
    
    def matches(self, act: "TraceAct") -> bool:
        """Проверяет, соответствует ли вызов функции BEGIN-акту.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если акт - BEGIN функции с соответствующим именем
        """
        return self.matches_node_kind(act) and self.matches_ast_details(act)
    
    def matches_node_kind(self, act: "TraceAct") -> bool:
        """Проверяет, что акт является BEGIN-узлом функции.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если акт - BEGIN-узел
        """
        from src.cfg.cfg import NodeKind
        return act.cfg_node.kind == NodeKind.BEGIN
    
    def matches_ast_details(self, act: "TraceAct") -> bool:
        """Проверяет соответствие имени функции.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если имя функции соответствует
        """
        # Извлекаем имя функции из акта
        func_name = self._get_function_name_from_act(act)
        if not func_name:
            return False
        
        # Проверяем соответствие имени функции
        return func_name == self.function_call.function_name
    
    def _get_function_name_from_act(self, act: "TraceAct") -> str | None:
        """Извлекает имя функции из акта трассы.
        
        Args:
            act: Акт трассы
            
        Returns:
            Имя функции или None
        """
        if not act.wrapped_ast or not isinstance(act.wrapped_ast.ast_node, dict):
            return None
        
        ast_node = act.wrapped_ast.ast_node
        node_type = ast_node.get('type', '')
        
        # Для function_definition ищем имя в declaration.name.name
        if node_type == 'function_definition':
            declaration = ast_node.get('declaration', {})
            name_node = declaration.get('name', {})
            if isinstance(name_node, dict):
                return name_node.get('name')
        
        # Для function_call ищем имя в function.name
        if node_type == 'function_call':
            func_node = ast_node.get('function', {})
            if isinstance(func_node, dict):
                return func_node.get('name')
        
        return None


class BindableFunctionReturn(BindableEvent):
    """Связываемое событие возврата из функции.
    
    Соответствует END-актам функций.
    """
    
    def __init__(self, event: FunctionReturn):
        """Инициализирует связываемое событие возврата из функции.
        
        Args:
            event: Событие возврата из функции
        """
        if not isinstance(event, FunctionReturn):
            raise TypeError(f"Expected FunctionReturn, got {type(event)}")
        super().__init__(event)
        self.function_return = event
    
    def matches(self, act: "TraceAct") -> bool:
        """Проверяет, соответствует ли возврат END-акту.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если акт - END функции с соответствующим именем
        """
        return self.matches_node_kind(act) and self.matches_ast_details(act)
    
    def matches_node_kind(self, act: "TraceAct") -> bool:
        """Проверяет, что акт является END-узлом функции.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если акт - END-узел
        """
        from src.cfg.cfg import NodeKind
        return act.cfg_node.kind == NodeKind.END
    
    def matches_ast_details(self, act: "TraceAct") -> bool:
        """Проверяет соответствие имени функции.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если имя функции соответствует
        """
        # Извлекаем имя функции из акта
        func_name = self._get_function_name_from_act(act)
        if not func_name:
            return False
        
        # Проверяем соответствие имени функции
        return func_name == self.function_return.function_name
    
    def _get_function_name_from_act(self, act: "TraceAct") -> str | None:
        """Извлекает имя функции из акта трассы.
        
        Args:
            act: Акт трассы
            
        Returns:
            Имя функции или None
        """
        if not act.wrapped_ast or not isinstance(act.wrapped_ast.ast_node, dict):
            return None
        
        ast_node = act.wrapped_ast.ast_node
        node_type = ast_node.get('type', '')
        
        # Для function_definition ищем имя в declaration.name.name
        if node_type == 'function_definition':
            declaration = ast_node.get('declaration', {})
            name_node = declaration.get('name', {})
            if isinstance(name_node, dict):
                return name_node.get('name')
        
        # Для function_call ищем имя в function.name (для END-актов рекурсивных вызовов)
        if node_type == 'function_call':
            func_node = ast_node.get('function', {})
            if isinstance(func_node, dict):
                return func_node.get('name')
        
        return None


class BindableConditionEvaluation(BindableEvent):
    """Связываемое событие вычисления условия.
    
    Соответствует ATOM-актам с ролью condition.
    """
    
    def __init__(self, event: ConditionEvaluation):
        """Инициализирует связываемое событие вычисления условия.
        
        Args:
            event: Событие вычисления условия
        """
        if not isinstance(event, ConditionEvaluation):
            raise TypeError(f"Expected ConditionEvaluation, got {type(event)}")
        super().__init__(event)
        self.condition_evaluation = event
    
    def matches(self, act: "TraceAct") -> bool:
        """Проверяет, соответствует ли вычисление условия ATOM-акту с условием.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если акт - ATOM-узел с условием и соответствующим ast_id
        """
        return self.matches_node_kind(act) and self.matches_ast_details(act)
    
    def matches_node_kind(self, act: "TraceAct") -> bool:
        """Проверяет, что акт является ATOM-узлом с условием.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если акт - ATOM-узел с условием
        """
        from src.cfg.cfg import NodeKind
        
        # Проверяем, что это ATOM-узел
        if act.cfg_node.kind != NodeKind.ATOM:
            return False
        
        # Проверяем, что узел является условием
        return act.cfg_node.is_condition()
    
    def matches_ast_details(self, act: "TraceAct") -> bool:
        """Проверяет соответствие ast_id.
        
        Args:
            act: Акт трассы для проверки
            
        Returns:
            True если ast_id соответствует
        """
        # Проверяем соответствие ast_id
        act_ast_id = self._get_ast_id_from_act(act)
        if act_ast_id is None:
            return False
        
        return act_ast_id == self.condition_evaluation.ast_id
    
    def _get_ast_id_from_act(self, act: "TraceAct") -> int | None:
        """Извлекает AST ID из акта трассы.
        
        Args:
            act: Акт трассы
            
        Returns:
            AST ID или None
        """
        if not act.wrapped_ast or not isinstance(act.wrapped_ast.ast_node, dict):
            return None
        
        return act.wrapped_ast.ast_node.get('id')


def create_bindable_events(runtime_events: list[RuntimeEvent]) -> list[BindableEvent]:
    """Создаёт список связываемых событий из списка runtime событий.
    
    Args:
        runtime_events: Список событий runtime трассировки
        
    Returns:
        Список связываемых событий в том же порядке
    """
    bindable_events: list[BindableEvent] = []
    
    for event in runtime_events:
        if isinstance(event, FunctionCall):
            bindable_events.append(BindableFunctionCall(event))
        elif isinstance(event, FunctionReturn):
            bindable_events.append(BindableFunctionReturn(event))
        elif isinstance(event, ConditionEvaluation):
            bindable_events.append(BindableConditionEvaluation(event))
        # PrintOutput не связывается с актами, пропускаем
    
    return bindable_events
