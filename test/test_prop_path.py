import json
from typing import Dict, Any
import pytest

from src.cfg import ASTNodeWrapper
from src.meaning_tree import to_dict

def test_astnodewrapper_1():
    """Базовые тесты для property_path с простыми операциями"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    res = root.get('branches', {'property_path':'branches/[0]/condition'})
    assert res is not None, "Result should not be None"
    assert res.ast_node == ast_json["body"][1]["branches"][0]["condition"]

    res2 = res.get('branches', {'property_path':'^ / [next] / condition'})
    assert res2.ast_node == ast_json["body"][1]["branches"][1]["condition"]

    res3 = res2.get('branches', {'property_path':'^ / [next] / condition'}, res2)
    assert res3.ast_node == ast_json["body"][1]["branches"][2]["condition"]

    res4 = res2.get('branches', {'property_path':'^ / [next] / condition'}, None)
    assert res4.ast_node == ast_json["body"][1]["branches"][2]["condition"]

    res5 = res2.get('body', {'property_path':'^ / body'}, res2)
    assert res5.ast_node == ast_json["body"][1]["branches"][1]["body"]


def test_complex_property_paths():
    """Тесты для сложных property_path с комбинациями операций"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Тест глубокой вложенности
    res = root.get('branches', {'property_path':'branches/[0]/condition/left_operand'})
    assert res is not None
    assert res.ast_node == ast_json["body"][1]["branches"][0]["condition"]["left_operand"]
    assert res.ast_node["name"] == "b"

    # Тест множественных переходов вверх и вниз - упрощенный
    res = root.get('branches', {'property_path':'branches/[0]/condition/left_operand'})
    res2 = res.get('branches', {'property_path':'^ / ^'})
    assert res2 is not None
    assert res2.ast_node == ast_json["body"][1]["branches"][0]  # first branch

    # Тест с пробелами в пути
    res = root.get('branches', {'property_path':'  branches  /  [0]  /  condition  '})
    assert res is not None
    assert res.ast_node == ast_json["body"][1]["branches"][0]["condition"]


def test_edge_cases():
    """Тесты для граничных случаев и ошибок"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Тест несуществующего пути
    res = root.get('branches', {'property_path':'nonexistent/path'})
    assert res is None

    # Тест несуществующего индекса
    res = root.get('branches', {'property_path':'branches/[999]/condition'})
    assert res is None

    # Тест пустого пути
    res = root.get('branches', {'property_path':''})
    assert res is None

    # Тест пути только с пробелами
    res = root.get('branches', {'property_path':'   '})
    assert res is None

    # Тест некорректного индекса
    res = root.get('branches', {'property_path':'branches/[abc]/condition'})
    assert res is None

    # Тест отрицательного индекса
    res = root.get('branches', {'property_path':'branches/[-1]/condition'})
    assert res is None


def test_navigation_operations():
    """Тесты для операций навигации ^ и [next]"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Тест перехода к родителю
    res = root.get('branches', {'property_path':'branches/[0]'})
    parent_res = res.get('branches', {'property_path':'^'})
    assert parent_res is not None
    assert parent_res.ast_node == ast_json["body"][1]["branches"]  # branches list

    # Тест перехода к следующему элементу
    res = root.get('branches', {'property_path':'branches/[0]'})
    next_res = res.get('branches', {'property_path':'[next]'})
    assert next_res is not None
    assert next_res.ast_node == ast_json["body"][1]["branches"][1]

    # Тест множественных переходов [next]
    res = root.get('branches', {'property_path':'branches/[0]'})
    next_res = res.get('branches', {'property_path':'[next]'})
    next_next_res = next_res.get('branches', {'property_path':'[next]'})
    assert next_next_res is not None
    assert next_next_res.ast_node == ast_json["body"][1]["branches"][2]

    # Тест перехода к родителю после [next]
    res = root.get('branches', {'property_path':'branches/[0]'})
    next_res = res.get('branches', {'property_path':'[next]'})
    parent_res = next_res.get('branches', {'property_path':'^'})
    assert parent_res is not None
    assert parent_res.ast_node == ast_json["body"][1]["branches"]  # branches list


def test_dict_access():
    """Тесты для доступа к словарям"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Тест доступа к свойствам словаря
    res = root.get('branches', {'property_path':'branches'})
    assert res is not None
    assert isinstance(res.ast_node, list)

    # Тест доступа к вложенным свойствам
    res = root.get('branches', {'property_path':'branches/[0]/condition/type'})
    assert res is not None
    assert res.ast_node == "gt_operator"

    # Тест доступа к несуществующему ключу
    res = root.get('branches', {'property_path':'branches/[0]/nonexistent'})
    assert res is None


def test_list_access():
    """Тесты для доступа к спискам"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Тест доступа к элементам списка
    res = root.get('branches', {'property_path':'branches/[0]'})
    assert res is not None
    assert res.ast_node == ast_json["body"][1]["branches"][0]

    # Тест доступа к последнему элементу
    last_index = len(ast_json["body"][1]["branches"]) - 1
    res = root.get('branches', {'property_path':f'branches/[{last_index}]'})
    assert res is not None
    assert res.ast_node == ast_json["body"][1]["branches"][last_index]

    # Тест доступа к несуществующему индексу
    res = root.get('branches', {'property_path':'branches/[999]'})
    assert res is None


def test_caching_behavior():
    """Тесты для проверки кэширования"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Первый доступ должен создать wrapper
    res1 = root.get('branches', {'property_path':'branches/[0]/condition'})
    assert res1 is not None

    # Второй доступ должен использовать кэш
    res2 = root.get('branches', {'property_path':'branches/[0]/condition'})
    assert res2 is not None
    assert res1 is res2  # Должны быть одним и тем же объектом

    # Проверяем, что children кэшируется правильно
    assert root.children is not None
    assert 'branches' in root.children


def test_previous_action_data():
    """Тесты для previous_action_data параметра"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Тест с previous_action_data для [next]
    first_branch = root.get('branches', {'property_path':'branches/[0]'})
    second_branch = first_branch.get('branches', {'property_path':'[next]'}, first_branch)
    assert second_branch is not None
    assert second_branch.ast_node == ast_json["body"][1]["branches"][1]

    # Тест без previous_action_data для [next] (должен использовать current)
    first_branch = root.get('branches', {'property_path':'branches/[0]'})
    second_branch = first_branch.get('branches', {'property_path':'[next]'}, None)
    assert second_branch is not None
    assert second_branch.ast_node == ast_json["body"][1]["branches"][1]


def test_mixed_operations():
    """Тесты для смешанных операций в одном пути"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Сложный путь: вниз -> вверх -> вниз - упрощенный
    res = root.get('branches', {'property_path':'branches/[0]/condition/left_operand'})
    complex_res = res.get('branches', {'property_path':'^ / ^'})
    assert complex_res is not None
    assert complex_res.ast_node == ast_json["body"][1]["branches"][0]  # first branch

    # Путь с множественными переходами вверх
    res = root.get('branches', {'property_path':'branches/[0]/condition'})
    up_up_res = res.get('branches', {'property_path':'^ / ^'})
    assert up_up_res is not None
    assert up_up_res.ast_node == ast_json["body"][1]["branches"]  # branches list


def test_error_handling():
    """Тесты для обработки ошибок"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Тест с None identification - должен найти по role
    res = root.get('branches', None)
    assert res is not None
    assert res.ast_node == ast_json["body"][1]["branches"]

    # Тест с пустым identification - должен найти по role
    res = root.get('branches', {})
    assert res is not None
    assert res.ast_node == ast_json["body"][1]["branches"]

    # Тест с некорректным типом identification
    res = root.get('branches', "invalid")
    assert res is None


def test_recursive_implementation():
    """Тесты для проверки рекурсивной реализации"""
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(ast_node=ast_json["body"][1])

    # Тест глубокой рекурсии
    deep_path = 'branches/[0]/condition/left_operand'
    res = root.get('branches', {'property_path': deep_path})
    assert res is not None
    assert res.ast_node["name"] == "b"

    # Тест рекурсии с навигацией - упрощенный
    recursive_path = 'branches/[0]/condition/left_operand/^/^'
    res = root.get('branches', {'property_path': recursive_path})
    assert res is not None
    assert res.ast_node == ast_json["body"][1]["branches"][0]  # first branch

    # Тест рекурсии с [next]
    next_recursive_path = 'branches/[0]/[next]/[next]/condition'
    res = root.get('branches', {'property_path': next_recursive_path})
    assert res is not None
    assert res.ast_node["type"] == "unary_operator"

