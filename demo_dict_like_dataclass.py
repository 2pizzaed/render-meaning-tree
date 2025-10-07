"""
Демонстрация возможностей DictLikeDataclass для создания дерева связанных объектов data-классов из JSON-данных.
"""

import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.common_utils import DictLikeDataclass, SelfValidatedEnum


# Определяем enum для типов узлов
class NodeType(SelfValidatedEnum):
    PROGRAM = "program_entry_point"
    IF_STATEMENT = "if_statement"
    ASSIGNMENT = "assignment_statement"
    IDENTIFIER = "identifier"
    INT_LITERAL = "int_literal"
    OPERATOR = "operator"


# Определяем dataclass для представления AST-узлов
@dataclass
class ASTNode(DictLikeDataclass):
    """Базовый класс для представления узлов AST"""
    type: str
    id: Optional[int] = None
    name: Optional[str] = None
    value: Optional[Any] = None
    body: Optional[List[Dict[str, Any]]] = None
    branches: Optional[List[Dict[str, Any]]] = None
    condition: Optional[Dict[str, Any]] = None
    target: Optional[Dict[str, Any]] = None
    left_operand: Optional[Dict[str, Any]] = None
    right_operand: Optional[Dict[str, Any]] = None
    statements: Optional[List[Dict[str, Any]]] = None
    elseBranch: Optional[Dict[str, Any]] = None
    repr: Optional[str] = None


def main():
    print("=" * 80)
    print("Демонстрация DictLikeDataclass")
    print("=" * 80)
    
    # Пример 1: Простой объект
    print("\n1. Создание простого объекта из JSON:")
    simple_data = {
        "type": "identifier",
        "id": 1,
        "name": "x"
    }
    print(f"   JSON данные: {simple_data}")
    
    simple_node = ASTNode.make(simple_data)
    print(f"   Результат: {simple_node}")
    print(f"   Доступ к полям: type={simple_node.type}, name={simple_node.name}, id={simple_node.id}")
    print(f"   Dict-доступ: type={simple_node['type']}, name={simple_node['name']}, id={simple_node['id']}")
    print(f"   Проверка наличия: 'name' in node = {'name' in simple_node}")
    print(f"   Get метод: node.get('name') = {simple_node.get('name')}, node.get('missing') = {simple_node.get('missing', 'default')}")
    
    # Пример 2: Объект с вложенной структурой
    print("\n2. Создание объекта с вложенной структурой:")
    complex_data = {
        "type": "assignment_statement",
        "id": 10,
        "target": {
            "type": "identifier",
            "id": 11,
            "name": "a"
        },
        "value": {
            "type": "int_literal",
            "id": 12,
            "value": 42,
            "repr": "DECIMAL"
        }
    }
    print(f"   JSON данные (сокращенно): {{'type': 'assignment_statement', 'target': {{...}}, 'value': {{...}}}}")
    
    complex_node = ASTNode.make(complex_data)
    print(f"   Результат: {complex_node}")
    print(f"   Вложенный target: {complex_node.target}")
    print(f"   Вложенный value: {complex_node.value}")
    
    # Демонстрация dict-like модификации
    print(f"\n   Dict-модификация:")
    print(f"   До изменения: name={complex_node['name']}")
    complex_node['name'] = "modified_assignment"
    print(f"   После изменения: name={complex_node['name']}, name={complex_node.name}")
    
    # Пример 3: Загрузка реального AST из файла
    print("\n3. Загрузка реального AST из файла ast.json:")
    try:
        with open("ast.json") as f:
            ast_data = json.load(f)
        
        print(f"   Тип корневого узла: {ast_data['type']}")
        print(f"   Количество элементов в body: {len(ast_data.get('body', []))}")
        
        root = ASTNode.make(ast_data)
        print(f"\n   Успешно создан объект: {root.type}")
        print(f"   ID корневого узла: {root.id}")
        print(f"   Количество элементов в body: {len(root.body) if root.body else 0}")
        
        if root.body and len(root.body) > 0:
            first_stmt = root.body[0]
            print(f"\n   Первый элемент в body:")
            print(f"     - type: {first_stmt.get('type')}")
            print(f"     - id: {first_stmt.get('id')}")
        
    except FileNotFoundError:
        print("   Файл ast.json не найден. Пропускаем этот пример.")
    except Exception as e:
        print(f"   Ошибка при загрузке AST: {e}")
    
    # Пример 4: Обработка ошибок
    print("\n4. Обработка ошибок:")
    
    # Пример 4.1: Отсутствует обязательное поле
    print("\n   4.1. Отсутствует обязательное поле 'type':")
    try:
        bad_data = {"id": 1, "name": "test"}
        ASTNode.make(bad_data)
    except ValueError as e:
        print(f"   [OK] Ошибка обнаружена: {e}")
    
    # Пример 4.2: Неизвестное поле
    print("\n   4.2. Неизвестное поле в данных:")
    try:
        bad_data = {"type": "test", "unknown_field": "value"}
        ASTNode.make(bad_data)
    except ValueError as e:
        print(f"   [OK] Ошибка обнаружена: {e}")
    
    # Пример 5: Использование с Enum
    print("\n5. Использование с Enum:")
    
    @dataclass
    class TypedNode(DictLikeDataclass):
        type: str
        node_type: Optional[NodeType] = None
    
    typed_data = {"type": "test", "node_type": "program_entry_point"}
    typed_node = TypedNode.make(typed_data)
    print(f"   Данные: {typed_data}")
    print(f"   Результат: node_type={typed_node.node_type}, тип={type(typed_node.node_type)}")
    print(f"   Сравнение: node_type == NodeType.PROGRAM -> {typed_node.node_type == NodeType.PROGRAM}")
    
    print("\n" + "=" * 80)
    print("Демонстрация завершена!")
    print("=" * 80)


if __name__ == "__main__":
    main()
