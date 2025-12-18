"""
Unit-тесты для подсистемы трассировки времени выполнения.
"""

import unittest

from src.runtime import (
    execute_with_trace,
    trace_function_calls,
    FunctionCall,
    FunctionReturn,
    PrintOutput,
    RuntimeTrace,
)


class TestExecuteWithTrace(unittest.TestCase):
    """Тесты для execute_with_trace."""
    
    def test_simple_function_call(self):
        """Тест: простой вызов функции отслеживается."""
        code = '''
def greet(name):
    return f"Hello, {name}!"

result = greet("World")
'''
        trace = execute_with_trace(code)
        
        self.assertIsInstance(trace, RuntimeTrace)
        self.assertEqual(len(trace.function_calls), 1)
        
        call = trace.function_calls[0]
        self.assertEqual(call.function_name, "greet")
        self.assertEqual(call.local_vars.get("name"), "World")
    
    def test_recursive_function_calls(self):
        """Тест: рекурсивные вызовы отслеживаются корректно."""
        code = '''
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

result = factorial(5)
'''
        trace = execute_with_trace(code)
        
        # Должно быть 5 вызовов: factorial(5), factorial(4), ..., factorial(1)
        self.assertEqual(len(trace.function_calls), 5)
        
        # Проверяем аргументы каждого вызова
        expected_args = [5, 4, 3, 2, 1]
        for i, call in enumerate(trace.function_calls):
            self.assertEqual(call.function_name, "factorial")
            self.assertEqual(call.local_vars.get("n"), expected_args[i])
    
    def test_function_return_values(self):
        """Тест: возвращаемые значения отслеживаются."""
        code = '''
def double(x):
    return x * 2

result = double(21)
'''
        trace = execute_with_trace(code)
        
        self.assertEqual(len(trace.function_returns), 1)
        
        ret = trace.function_returns[0]
        self.assertEqual(ret.function_name, "double")
        self.assertEqual(ret.return_value, 42)
    
    def test_print_output_captured(self):
        """Тест: вывод print захватывается."""
        code = '''
def say_hello():
    print("Hello!")
    print("World!")

say_hello()
'''
        trace = execute_with_trace(code)
        
        self.assertEqual(len(trace.print_outputs), 2)
        self.assertEqual(trace.print_outputs[0].text, "Hello!\n")
        self.assertEqual(trace.print_outputs[1].text, "World!\n")
    
    def test_print_with_multiple_args(self):
        """Тест: print с несколькими аргументами."""
        code = '''
def show_sum(a, b):
    print("Sum:", a + b)

show_sum(3, 4)
'''
        trace = execute_with_trace(code)
        
        self.assertEqual(len(trace.print_outputs), 1)
        self.assertIn("Sum: 7", trace.print_outputs[0].text)
    
    def test_multiple_functions(self):
        """Тест: несколько функций отслеживаются."""
        code = '''
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

x = add(2, 3)
y = multiply(x, 4)
'''
        trace = execute_with_trace(code)
        
        self.assertEqual(len(trace.function_calls), 2)
        
        # Проверяем, что обе функции зафиксированы
        func_names = [c.function_name for c in trace.function_calls]
        self.assertIn("add", func_names)
        self.assertIn("multiply", func_names)
    
    def test_nested_function_calls(self):
        """Тест: вложенные вызовы функций."""
        code = '''
def inner(x):
    return x + 1

def outer(x):
    return inner(x) * 2

result = outer(5)
'''
        trace = execute_with_trace(code)
        
        # Должны быть вызовы outer и inner
        self.assertEqual(len(trace.function_calls), 2)
        
        func_names = [c.function_name for c in trace.function_calls]
        self.assertEqual(func_names, ["outer", "inner"])
    
    def test_exception_captured(self):
        """Тест: исключения фиксируются в трассе."""
        code = '''
def divide(a, b):
    return a / b

result = divide(1, 0)
'''
        trace = execute_with_trace(code)
        
        self.assertIsNotNone(trace.exception)
        self.assertIsInstance(trace.exception, ZeroDivisionError)
        self.assertIsNotNone(trace.exception_traceback)
    
    def test_syntax_error_captured(self):
        """Тест: синтаксические ошибки фиксируются."""
        code = '''
def broken(
    return 1
'''
        trace = execute_with_trace(code)
        
        self.assertIsNotNone(trace.exception)
        self.assertIsInstance(trace.exception, SyntaxError)
    
    def test_empty_code(self):
        """Тест: пустой код не вызывает ошибок."""
        code = ''
        trace = execute_with_trace(code)
        
        self.assertEqual(len(trace.events), 0)
        self.assertIsNone(trace.exception)
    
    def test_code_without_functions(self):
        """Тест: код без функций выполняется корректно."""
        code = '''
x = 1 + 2
y = x * 3
print("Result:", y)
'''
        trace = execute_with_trace(code)
        
        self.assertEqual(len(trace.function_calls), 0)
        # print вызван из модуля, не из функции пользователя
        # но мы его всё равно должны захватить если он из целевого файла


class TestTraceFunctionCalls(unittest.TestCase):
    """Тесты для trace_function_calls."""
    
    def test_filter_by_function_name(self):
        """Тест: фильтрация по имени функции."""
        code = '''
def foo(x):
    return x

def bar(y):
    return foo(y + 1)

bar(5)
'''
        # Только вызовы foo
        calls = trace_function_calls(code, function_name="foo")
        
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['name'], 'foo')
        self.assertEqual(calls[0]['args'].get('x'), 6)
    
    def test_return_format(self):
        """Тест: формат возвращаемых данных."""
        code = '''
def greet(name, greeting="Hello"):
    return f"{greeting}, {name}!"

greet("Alice", greeting="Hi")
'''
        calls = trace_function_calls(code)
        
        self.assertEqual(len(calls), 1)
        call = calls[0]
        
        self.assertIn('name', call)
        self.assertIn('args', call)
        self.assertIn('line', call)
        self.assertIn('order', call)
        
        self.assertEqual(call['args'].get('name'), "Alice")
        self.assertEqual(call['args'].get('greeting'), "Hi")


class TestRuntimeTrace(unittest.TestCase):
    """Тесты для класса RuntimeTrace."""
    
    def test_describe_output(self):
        """Тест: метод describe возвращает читаемое описание."""
        code = '''
def fib(n):
    if n <= 2:
        return n
    return fib(n - 1) + fib(n - 2)

print("fib(4) =", fib(4))
'''
        trace = execute_with_trace(code)
        description = trace.describe()
        
        self.assertIn("CALL fib", description)
        self.assertIn("RETURN fib", description)
        self.assertIn("PRINT:", description)
        self.assertIn("Всего событий:", description)
    
    def test_event_ordering(self):
        """Тест: события нумеруются последовательно."""
        code = '''
def a():
    return 1

def b():
    return 2

a()
b()
'''
        trace = execute_with_trace(code)
        
        # Проверяем, что order монотонно возрастает
        orders = [e.order for e in trace.events]
        self.assertEqual(orders, sorted(orders))
        self.assertEqual(orders[0], 1)


class TestMutualRecursion(unittest.TestCase):
    """Тесты для взаимной рекурсии."""
    
    def test_mutual_recursion_traced(self):
        """Тест: взаимная рекурсия отслеживается."""
        code = '''
def is_even(n):
    if n == 0:
        return True
    return is_odd(n - 1)

def is_odd(n):
    if n == 0:
        return False
    return is_even(n - 1)

result = is_even(4)
'''
        trace = execute_with_trace(code)
        
        # is_even(4) -> is_odd(3) -> is_even(2) -> is_odd(1) -> is_even(0)
        self.assertEqual(len(trace.function_calls), 5)
        
        func_names = [c.function_name for c in trace.function_calls]
        self.assertEqual(func_names, ['is_even', 'is_odd', 'is_even', 'is_odd', 'is_even'])


class TestEnrichTraceWithRuntime(unittest.TestCase):
    """Тесты для функции enrich_trace_with_runtime и интеграции с TraceAct."""
    
    def test_runtime_info_model(self):
        """Тест: RuntimeInfo dataclass работает корректно."""
        from src.cfg.cfg import RuntimeInfo
        
        # Создаём RuntimeInfo с данными
        info = RuntimeInfo(
            function_args={'n': 5, 'x': 'test'},
            return_value=120,
            print_outputs=['Hello', 'World'],
            function_name='factorial'
        )
        
        self.assertEqual(info.function_args, {'n': 5, 'x': 'test'})
        self.assertEqual(info.return_value, 120)
        self.assertEqual(info.print_outputs, ['Hello', 'World'])
        self.assertEqual(info.function_name, 'factorial')
    
    def test_runtime_info_defaults(self):
        """Тест: RuntimeInfo имеет корректные значения по умолчанию."""
        from src.cfg.cfg import RuntimeInfo
        
        info = RuntimeInfo()
        
        self.assertIsNone(info.function_args)
        self.assertIsNone(info.return_value)
        self.assertIsNone(info.print_outputs)
        self.assertIsNone(info.function_name)
    
    def test_export_trace_acts_with_runtime_info(self):
        """Тест: export_trace_acts корректно экспортирует runtime_info."""
        from src.cfg.cfg import RuntimeInfo, TraceAct, Node, NodeKind, Metadata
        from src.cfg.ast_wrapper import ASTNodeWrapper
        from src.cfg.condition_exporter import export_trace_acts
        
        # Создаём минимальный TraceAct с runtime_info
        wrapped_ast = ASTNodeWrapper(ast_node={'id': 1, 'type': 'function_definition'})
        node = Node(
            id='test_node',
            kind=NodeKind.BEGIN,
            role_in_construct='test',
            metadata=Metadata(wrapped_ast=wrapped_ast)
        )
        
        trace_act = TraceAct(
            wrapped_ast=wrapped_ast,
            cfg_node=node,
            action_spec=None,
            corresponding_end=None,
            is_known_correct=False,
            runtime_info=RuntimeInfo(
                function_name='test_func',
                function_args={'a': 1, 'b': 2},
                return_value=3,
            )
        )
        
        result = export_trace_acts([trace_act], scenario_name='test')
        
        self.assertEqual(result['scenario_name'], 'test')
        self.assertEqual(len(result['trace']), 1)
        
        item = result['trace'][0]
        self.assertIn('runtime_info', item)
        self.assertEqual(item['runtime_info']['function_name'], 'test_func')
        self.assertEqual(item['runtime_info']['function_args'], {'a': 1, 'b': 2})
        self.assertEqual(item['runtime_info']['return_value'], 3)
    
    def test_export_trace_acts_without_runtime_info(self):
        """Тест: export_trace_acts работает без runtime_info."""
        from src.cfg.cfg import TraceAct, Node, NodeKind, Metadata
        from src.cfg.ast_wrapper import ASTNodeWrapper
        from src.cfg.condition_exporter import export_trace_acts
        
        wrapped_ast = ASTNodeWrapper(ast_node={'id': 1, 'type': 'test'})
        node = Node(
            id='test_node',
            kind=NodeKind.ATOM,
            role_in_construct='test',
            metadata=Metadata(wrapped_ast=wrapped_ast)
        )
        
        trace_act = TraceAct(
            wrapped_ast=wrapped_ast,
            cfg_node=node,
            action_spec=None,
            corresponding_end=None,
            is_known_correct=False,
            runtime_info=None  # Нет runtime_info
        )
        
        result = export_trace_acts([trace_act])
        
        item = result['trace'][0]
        self.assertNotIn('runtime_info', item)
    
    def test_safe_json_value_conversion(self):
        """Тест: _safe_json_value корректно преобразует значения."""
        from src.cfg.condition_exporter import _safe_json_value
        
        # Простые типы
        self.assertEqual(_safe_json_value(42), 42)
        self.assertEqual(_safe_json_value(3.14), 3.14)
        self.assertEqual(_safe_json_value('hello'), 'hello')
        self.assertEqual(_safe_json_value(True), True)
        self.assertEqual(_safe_json_value(None), None)
        
        # Списки
        self.assertEqual(_safe_json_value([1, 2, 3]), [1, 2, 3])
        
        # Словари
        self.assertEqual(_safe_json_value({'a': 1}), {'a': 1})
        
        # Вложенные структуры
        nested = {'list': [1, 2], 'dict': {'x': 'y'}}
        self.assertEqual(_safe_json_value(nested), nested)


class TestMatcherIntegration(unittest.TestCase):
    """Интеграционные тесты для matcher с реальным выполнением."""
    
    def test_enrich_preserves_trace_structure(self):
        """Тест: enrich_trace_with_runtime сохраняет структуру трассы."""
        from src.runtime import enrich_trace_with_runtime
        from src.runtime.models import RuntimeTrace, FunctionCall, FunctionReturn
        from src.cfg.cfg import TraceAct, Node, NodeKind, Metadata
        from src.cfg.ast_wrapper import ASTNodeWrapper
        
        # Создаём пустую runtime трассу
        runtime_trace = RuntimeTrace()
        
        # Создаём простой TraceAct
        wrapped_ast = ASTNodeWrapper(ast_node={'id': 1, 'type': 'test'})
        node = Node(
            id='node1',
            kind=NodeKind.ATOM,
            role_in_construct='test',
            metadata=Metadata(wrapped_ast=wrapped_ast)
        )
        trace_act = TraceAct(
            wrapped_ast=wrapped_ast,
            cfg_node=node,
            action_spec=None,
            corresponding_end=None,
            is_known_correct=False
        )
        
        trace_acts = [trace_act]
        
        # Создаём mock ASTNodeAnalyzer
        class MockAnalyzer:
            user_defined_function_names = set()
            def get_code_line_number_by_id(self, ast_id):
                return 1
        
        # Обогащаем (с пустой runtime трассой)
        result = enrich_trace_with_runtime(trace_acts, runtime_trace, MockAnalyzer())
        
        # Проверяем, что структура сохранилась
        self.assertEqual(len(result), 1)
        self.assertIs(result[0], trace_act)


if __name__ == '__main__':
    unittest.main()
