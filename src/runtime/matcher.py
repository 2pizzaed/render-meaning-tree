"""
Модуль для сопоставления runtime событий с актами трассы TraceAct.

Связывает данные, собранные при реальном выполнении программы (вызовы функций,
возвраты, вывод print), с актами статической трассы, построенной по CFG.
"""

from typing import Any

from src.ast_analyzer import ASTNodeAnalyzer
from src.cfg.cfg import NodeKind, RuntimeInfo, TraceAct
from src.runtime.models import (
    FunctionCall,
    FunctionReturn,
    PrintOutput,
    RuntimeTrace,
)


def enrich_trace_with_runtime(
    trace_acts: list[TraceAct],
    runtime_trace: RuntimeTrace,
    ast_analyzer: ASTNodeAnalyzer,
) -> list[TraceAct]:
    """Обогащает акты трассы информацией из runtime выполнения.
    
    Сопоставляет события RuntimeTrace с актами TraceAct по:
    - Номеру строки (из AST через ast_analyzer)
    - Типу узла (BEGIN для вызовов, END для возвратов)
    - Имени функции
    
    Args:
        trace_acts: Список актов трассы для обогащения
        runtime_trace: Трасса runtime выполнения с событиями
        ast_analyzer: Анализатор AST для получения номеров строк
        
    Returns:
        Тот же список trace_acts с заполненными полями runtime_info
    """
    if not runtime_trace or not runtime_trace.events:
        return trace_acts
    
    # Строим индекс актов по номеру строки и типу
    acts_by_line = _build_acts_index(trace_acts, ast_analyzer)
    
    # Получаем имена функций, определённых в файле
    user_functions = ast_analyzer.user_defined_function_names
    
    # Создаём итераторы для событий каждого типа
    call_events = iter(runtime_trace.function_calls)
    return_events = iter(runtime_trace.function_returns)
    print_events = list(runtime_trace.print_outputs)
    
    # Сопоставляем вызовы функций с BEGIN актами
    _match_function_calls(trace_acts, call_events, acts_by_line, user_functions)
    
    # Сопоставляем возвраты с END актами
    _match_function_returns(trace_acts, return_events, acts_by_line, user_functions)
    
    # Сопоставляем print с ближайшими актами
    _match_print_outputs(trace_acts, print_events, acts_by_line, ast_analyzer)
    
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


def _match_function_calls(
    trace_acts: list[TraceAct],
    call_events: iter,
    acts_by_line: dict[int, list[tuple[int, TraceAct]]],
    user_functions: set[str],
) -> None:
    """Сопоставляет события вызовов функций с актами трассы.
    
    Для каждого BEGIN-акта с функцией из user_functions находит
    соответствующий FunctionCall и заполняет runtime_info.
    
    Args:
        trace_acts: Список актов (изменяется in-place)
        call_events: Итератор событий FunctionCall
        acts_by_line: Индекс актов по строкам
        user_functions: Имена пользовательских функций
    """
    # Собираем все call события в список для повторного использования
    calls_list = list(call_events)
    call_idx = 0
    
    for act in trace_acts:
        if act.cfg_node.kind != NodeKind.BEGIN:
            continue
        
        func_name = _get_function_name_from_act(act)
        if not func_name or func_name not in user_functions:
            continue
        
        # Ищем следующий call для этой функции
        while call_idx < len(calls_list):
            call = calls_list[call_idx]
            if call.function_name == func_name:
                # Нашли соответствие
                act.runtime_info = RuntimeInfo(
                    function_args=call.local_vars.copy() if call.local_vars else None,
                    function_name=func_name,
                )
                call_idx += 1
                break
            call_idx += 1


def _match_function_returns(
    trace_acts: list[TraceAct],
    return_events: iter,
    acts_by_line: dict[int, list[tuple[int, TraceAct]]],
    user_functions: set[str],
) -> None:
    """Сопоставляет события возвратов с актами трассы.
    
    Для каждого END-акта с функцией из user_functions находит
    соответствующий FunctionReturn и заполняет runtime_info.
    
    Args:
        trace_acts: Список актов (изменяется in-place)
        return_events: Итератор событий FunctionReturn
        acts_by_line: Индекс актов по строкам
        user_functions: Имена пользовательских функций
    """
    # Собираем все return события в список
    returns_list = list(return_events)
    return_idx = 0
    
    for act in trace_acts:
        if act.cfg_node.kind != NodeKind.END:
            continue
        
        func_name = _get_function_name_from_act(act)
        if not func_name or func_name not in user_functions:
            continue
        
        # Ищем следующий return для этой функции
        while return_idx < len(returns_list):
            ret = returns_list[return_idx]
            if ret.function_name == func_name:
                # Нашли соответствие
                if act.runtime_info is None:
                    act.runtime_info = RuntimeInfo(function_name=func_name)
                act.runtime_info.return_value = ret.return_value
                return_idx += 1
                break
            return_idx += 1


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
