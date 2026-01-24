"""
Модуль для сопоставления runtime событий с актами трассы TraceAct.

Связывает данные, собранные при реальном выполнении программы (вызовы функций,
возвраты, вывод print, условия), с актами статической трассы, построенной по CFG.

Использует стратегию последовательного связывания:
- Проходит трассу от начала до конца
- При требовании значения запрашивает следующее неиспользованное событие из runtime trace
- Выполняет строгую валидацию соответствия
"""

from typing import Any

from src.ast_analyzer import ASTNodeAnalyzer
from src.cfg.cfg import NodeKind, RuntimeInfo, TraceAct
from src.runtime.bindable_events import (
    BindableConditionEvaluation,
    BindableEvent,
    BindableFunctionCall,
    BindableFunctionReturn,
    create_bindable_events,
)
from src.runtime.models import (
    PrintOutput,
    RuntimeTrace,
)


def enrich_trace_with_runtime(
    trace_acts: list[TraceAct],
    runtime_trace: RuntimeTrace,
    ast_analyzer: ASTNodeAnalyzer,
) -> list[TraceAct]:
    """Обогащает акты трассы информацией из runtime выполнения.
    
    Использует стратегию последовательного связывания:
    - Проходит трассу от начала до конца
    - При требовании значения запрашивает следующее неиспользованное событие
    - Выполняет строгую валидацию соответствия
    
    Args:
        trace_acts: Список актов трассы для обогащения
        runtime_trace: Трасса runtime выполнения с событиями
        ast_analyzer: Анализатор AST для получения номеров строк
        
    Returns:
        Тот же список trace_acts с заполненными полями runtime_info
        
    Raises:
        ValueError: Если событие не соответствует ожидаемому акту
        RuntimeError: Если требуемое событие отсутствует в runtime trace
    """
    if not runtime_trace or not runtime_trace.events:
        return trace_acts
    
    # Создаём список связываемых событий из runtime trace (уже упорядоченных)
    bindable_events = create_bindable_events(runtime_trace.events)
    
    # Получаем имена функций, определённых в файле
    user_functions = ast_analyzer.user_defined_function_names
    
    # Последовательно проходим по трассе
    for act in trace_acts:
        # Определяем, какое событие требуется для этого акта
        required_event_type = _get_required_event_type(act, user_functions)
        
        if required_event_type is None:
            # Для этого акта не требуется событие, пропускаем
            continue
        
        # Ищем следующее неиспользованное событие соответствующего типа
        bindable_event = _find_next_unused_event(
            bindable_events, required_event_type
        )
        
        if bindable_event is None:
            # Событие отсутствует - это ошибка построения сценария
            raise RuntimeError(
                f"Required {required_event_type.__name__} event not found in runtime trace "
                f"for act at position {trace_acts.index(act)} "
                f"(node_kind={act.cfg_node.kind.value if act.cfg_node else None})"
            )
        
        # Строгая валидация: проверяем тип события (BEGIN/END/ATOM)
        if not bindable_event.matches_node_kind(act):
            raise ValueError(
                f"Event type mismatch at act position {trace_acts.index(act)}: "
                f"expected {required_event_type.__name__} for node_kind={act.cfg_node.kind.value if act.cfg_node else None}, "
                f"but got {bindable_event.event.describe()}"
            )
        
        # Мягкая валидация: проверяем соответствие AST деталей (имя функции, ast_id)
        # Если не соответствует, выводим warning, но продолжаем работу
        if not bindable_event.matches_ast_details(act):
            import warnings
            act_pos = trace_acts.index(act)
            warnings.warn(
                f"AST details mismatch at act position {act_pos}: "
                f"Event {bindable_event.event.describe()} does not match AST details of act "
                f"(node_kind={act.cfg_node.kind.value if act.cfg_node else None}). "
                f"Continuing with binding anyway.",
                stacklevel=2
            )
        
        # Привязываем событие к акту
        _bind_event_to_act(bindable_event, act)
        ### TODO: ADD logging on each bind

        
        # Помечаем событие как использованное
        bindable_event.mark_used()
    
    # Сопоставляем print с ближайшими актами (отдельная логика, не требует последовательности)
    acts_by_line = _build_acts_index(trace_acts, ast_analyzer)
    _match_print_outputs(trace_acts, list(runtime_trace.print_outputs), acts_by_line, ast_analyzer)
    
    return trace_acts


def _build_acts_index(
    trace_acts: list[TraceAct],
    ast_analyzer: ASTNodeAnalyzer,
) -> dict[int, list[tuple[int, TraceAct]]]:
    """Строит индекс актов по номеру строки.
    
    Args:
        trace_acts: Список актов трассы
        ast_analyzer: Анализатор AST
        
    Returns:
        Словарь {line_number: [(position, trace_act), ...]}
    """
    index: dict[int, list[tuple[int, TraceAct]]] = {}
    
    for position, act in enumerate(trace_acts):
        line = _get_line_number(act, ast_analyzer)
        if line is not None:
            if line not in index:
                index[line] = []
            index[line].append((position, act))
    
    return index


def _get_line_number(act: TraceAct, ast_analyzer: ASTNodeAnalyzer) -> int | None:
    """Получает номер строки для акта трассы.
    
    Args:
        act: Акт трассы
        ast_analyzer: Анализатор AST
        
    Returns:
        Номер строки (1-based) или None
    """
    if not act.wrapped_ast or not isinstance(act.wrapped_ast.ast_node, dict):
        return None
    
    ast_id = act.wrapped_ast.ast_node.get('id')
    if ast_id is None:
        return None
    
    return ast_analyzer.get_code_line_number_by_id(ast_id)


def _get_function_name_from_act(act: TraceAct) -> str | None:
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


def _get_required_event_type(
    act: TraceAct, user_functions: set[str]
) -> type[BindableEvent] | None:
    """Определяет тип события, требуемого для акта трассы.
    
    Args:
        act: Акт трассы
        user_functions: Множество имён пользовательских функций
        
    Returns:
        Тип требуемого события или None, если событие не требуется
    """
    if act.cfg_node.kind == NodeKind.BEGIN:
        # BEGIN-акт функции требует FunctionCall
        func_name = _get_function_name_from_act(act)
        if func_name and func_name in user_functions:
            return BindableFunctionCall
    
    elif act.cfg_node.kind == NodeKind.END:
        # END-акт функции требует FunctionReturn
        func_name = _get_function_name_from_act(act)
        if func_name and func_name in user_functions:
            return BindableFunctionReturn
    
    elif act.cfg_node.kind == NodeKind.ATOM:
        # ATOM-акт с условием требует ConditionEvaluation
        if act.cfg_node.is_condition():
            return BindableConditionEvaluation
    
    return None


def _find_next_unused_event(
    bindable_events: list[BindableEvent],
    event_type: type[BindableEvent],
) -> BindableEvent | None:
    """Находит следующее неиспользованное событие указанного типа.
    
    Args:
        bindable_events: Список связываемых событий
        event_type: Тип требуемого события
        
    Returns:
        Первое неиспользованное событие указанного типа или None
    """
    for bindable_event in bindable_events:
        if not bindable_event.used and isinstance(bindable_event, event_type):
            return bindable_event
    return None


def _bind_event_to_act(bindable_event: BindableEvent, act: TraceAct) -> None:
    """Привязывает событие к акту трассы, заполняя runtime_info.
    
    Args:
        bindable_event: Связываемое событие
        act: Акт трассы
    """
    if isinstance(bindable_event, BindableFunctionCall):
        # Привязываем аргументы вызова функции
        call = bindable_event.function_call
        act.runtime_info = RuntimeInfo(
            function_args=call.local_vars.copy() if call.local_vars else None,
            function_name=call.function_name,
        )
    
    elif isinstance(bindable_event, BindableFunctionReturn):
        # Привязываем возвращаемое значение (None не присваиваем)
        ret = bindable_event.function_return
        if act.runtime_info is None:
            act.runtime_info = RuntimeInfo(function_name=ret.function_name)
        
        # Фиксируем все возвраты, но не отображаем None
        if ret.return_value is not None:
            act.runtime_info.return_value = ret.return_value
        # Если return_value is None, не присваиваем (требование "None не отображать")
    
    elif isinstance(bindable_event, BindableConditionEvaluation):
        # Привязываем значение условия
        cond = bindable_event.condition_evaluation
        from src.cfg.abstractions import OptionalBoolValue
        
        # Преобразуем bool в OptionalBoolValue
        if cond.value:
            act.condition_value = OptionalBoolValue.true
        else:
            act.condition_value = OptionalBoolValue.false


def _match_print_outputs(
    trace_acts: list[TraceAct],
    print_events: list[PrintOutput],
    acts_by_line: dict[int, list[tuple[int, TraceAct]]],
    ast_analyzer: ASTNodeAnalyzer,
) -> None:
    """Сопоставляет события print с актами трассы.
    
    Print привязывается к акту на той же строке или к ближайшему
    предшествующему акту в трассе.
    
    Args:
        trace_acts: Список актов (изменяется in-place)
        print_events: Список событий PrintOutput
        acts_by_line: Индекс актов по строкам
        ast_analyzer: Анализатор AST
    """
    if not print_events:
        return
    
    # Группируем print по строкам
    prints_by_line: dict[int, list[str]] = {}
    for p in print_events:
        line = p.line_number
        if line not in prints_by_line:
            prints_by_line[line] = []
        prints_by_line[line].append(p.text.rstrip('\n'))
    
    # Для каждой строки с print находим акт
    for line, outputs in prints_by_line.items():
        # Ищем акт на этой строке
        acts_on_line = acts_by_line.get(line, [])
        
        if acts_on_line:
            # Берём последний акт на этой строке
            _, act = acts_on_line[-1]
            if act.runtime_info is None:
                act.runtime_info = RuntimeInfo()
            if act.runtime_info.print_outputs is None:
                act.runtime_info.print_outputs = []
            act.runtime_info.print_outputs.extend(outputs)
        else:
            # Ищем ближайший акт на предыдущей строке
            for prev_line in range(line - 1, 0, -1):
                acts_on_prev = acts_by_line.get(prev_line, [])
                if acts_on_prev:
                    _, act = acts_on_prev[-1]
                    if act.runtime_info is None:
                        act.runtime_info = RuntimeInfo()
                    if act.runtime_info.print_outputs is None:
                        act.runtime_info.print_outputs = []
                    act.runtime_info.print_outputs.extend(outputs)
                    break


def enrich_trace_from_scenario(
    trace_acts: list[TraceAct],
    scenario: dict[str, Any],
    ast_analyzer: ASTNodeAnalyzer,
) -> list[TraceAct]:
    """Обогащает акты трассы данными из сценария без runtime выполнения.
    
    Использует ту же стратегию последовательного связывания, что и enrich_trace_with_runtime,
    но берет данные из сохраненного сценария вместо RuntimeTrace.
    
    Args:
        trace_acts: Список актов трассы для обогащения
        scenario: Словарь сценария с полем events
        ast_analyzer: Анализатор AST для получения номеров строк
        
    Returns:
        Тот же список trace_acts с заполненными полями runtime_info и condition_value
        
    Raises:
        ValueError: Если событие не соответствует ожидаемому акту
        RuntimeError: Если требуемое событие отсутствует в сценарии
    """
    from src.cfg.condition_exporter import extract_runtime_data_from_scenario
    from src.runtime.models import (
        ConditionEvaluation,
        FunctionCall,
        FunctionReturn,
    )
    
    # Извлекаем runtime данные из сценария
    runtime_data = extract_runtime_data_from_scenario(scenario)
    
    # Преобразуем события из сценария в RuntimeEvent объекты
    events = []
    
    # Преобразуем conditions
    for cond_data in runtime_data["conditions"]:
        # Обрабатываем значение условия (может быть строкой "true"/"false" или bool)
        value = cond_data.get("value")
        if isinstance(value, str):
            bool_value = value.lower() == "true"
        else:
            bool_value = bool(value) if value is not None else False
        
        event = ConditionEvaluation(
            line_number=cond_data.get("line_number", 0),
            ast_id=cond_data.get("ast_id", 0),
            value=bool_value,
            condition_type=cond_data.get("condition_type", ""),  # Поддерживает 'for_each', 'range_for', 'if', 'while', etc.
            expression_text=cond_data.get("expression_text", ""),
        )
        event.order = cond_data.get("order", 0)
        events.append(event)
    
    # Преобразуем function_calls
    for call_data in runtime_data["function_calls"]:
        args_dict = call_data.get("args", {})
        if isinstance(args_dict, str):
            # Если args сохранены как JSON-строка, нужно распарсить
            import json
            try:
                args_dict = json.loads(args_dict)
            except Exception:
                args_dict = {}
        elif not isinstance(args_dict, dict):
            args_dict = {}
        
        event = FunctionCall(
            line_number=call_data.get("line_number", 0),
            function_name=call_data.get("function_name", ""),
            local_vars=args_dict,
            call_line=call_data.get("call_line"),
        )
        event.order = call_data.get("order", 0)
        events.append(event)
    
    # Преобразуем function_returns
    for ret_data in runtime_data["function_returns"]:
        return_value = ret_data.get("return_value")
        # return_value может быть None, что нормально (фиксируем все возвраты)
        # Значение уже в правильном формате из JSON
        
        event = FunctionReturn(
            line_number=ret_data.get("line_number", 0),
            function_name=ret_data.get("function_name", ""),
            return_value=return_value,
        )
        event.order = ret_data.get("order", 0)
        events.append(event)
    
    # Сортируем события по order
    events.sort(key=lambda e: e.order)
    
    # Создаём виртуальный RuntimeTrace для использования существующей логики
    from src.runtime.models import RuntimeTrace
    virtual_trace = RuntimeTrace()
    virtual_trace.events = events
    
    # Используем существующую функцию enrich_trace_with_runtime
    return enrich_trace_with_runtime(trace_acts, virtual_trace, ast_analyzer)


def enrich_single_scenario(
    trace_acts: list[TraceAct],
    source_code: str,
    filename: str,
    ast_analyzer: ASTNodeAnalyzer,
) -> list[TraceAct]:
    """Удобная функция для обогащения трассы одного сценария.
    
    Выполняет код и обогащает акты трассы в один вызов.
    
    Args:
        trace_acts: Список актов трассы
        source_code: Исходный код программы
        filename: Имя файла (для трассировщика)
        ast_analyzer: Анализатор AST
        
    Returns:
        Список актов с заполненными runtime_info
    """
    from src.runtime.executor import execute_with_trace
    
    runtime_trace = execute_with_trace(source_code, filename)
    return enrich_trace_with_runtime(trace_acts, runtime_trace, ast_analyzer)
