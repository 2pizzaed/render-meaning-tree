"""
Демонстрация упрощенной загрузки JSON с использованием DictLikeDataclass
"""

import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.common_utils import DictLikeDataclass, SelfValidatedEnum


def demo_ast_loading():
    """Демонстрация загрузки AST из JSON"""
    print("=" * 80)
    print("Демонстрация упрощенной загрузки AST из JSON")
    print("=" * 80)
    
    try:
        with open("test/ast.json", "r") as f:
            ast_data = json.load(f)
        
        # Определяем dataclass для AST узлов
        @dataclass
        class ASTNode(DictLikeDataclass):
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
            operand: Optional[Dict[str, Any]] = None
            statements: Optional[List[Dict[str, Any]]] = None
            elseBranch: Optional[Dict[str, Any]] = None
            repr: Optional[str] = None
        
        print("\n1. Загрузка AST из JSON с помощью DictLikeDataclass:")
        print(f"   Исходные данные: type={ast_data['type']}, id={ast_data['id']}")
        
        # Загружаем AST используя DictLikeDataclass
        ast = ASTNode.make(ast_data)
        
        print(f"   Результат: type={ast.type}, id={ast.id}")
        print(f"   Количество элементов в body: {len(ast.body) if ast.body else 0}")
        
        print("\n2. Dict-like доступ к данным:")
        print(f"   ast['type'] = {ast['type']}")
        print(f"   ast['id'] = {ast['id']}")
        print(f"   len(ast['body']) = {len(ast['body']) if ast['body'] else 0}")
        
        print("\n3. Доступ к вложенным структурам:")
        if ast.body and len(ast.body) > 0:
            first_stmt = ast.body[0]
            print(f"   Первый элемент: type={first_stmt['type']}, id={first_stmt['id']}")
            print(f"   Target: {first_stmt['target']['name'] if first_stmt.get('target') else 'None'}")
            print(f"   Value: {first_stmt['value']['value'] if first_stmt.get('value') else 'None'}")
        
        print("\n4. Модификация данных через dict-доступ:")
        if ast.body and len(ast.body) > 0:
            original_name = ast['body'][0]['target']['name']
            print(f"   Оригинальное имя: {original_name}")
            
            ast['body'][0]['target']['name'] = "modified_variable"
            print(f"   После изменения: {ast['body'][0]['target']['name']}")
            print(f"   Синхронизация с атрибутом: {ast.body[0]['target']['name']}")
            
            # Восстанавливаем оригинальное значение
            ast['body'][0]['target']['name'] = original_name
            print(f"   После восстановления: {ast['body'][0]['target']['name']}")
        
        print("\n5. Dict-like операции:")
        print(f"   'type' in ast: {'type' in ast}")
        print(f"   'nonexistent' in ast: {'nonexistent' in ast}")
        print(f"   ast.get('type'): {ast.get('type')}")
        print(f"   ast.get('nonexistent', 'default'): {ast.get('nonexistent', 'default')}")
        
        print("\n6. Доступ к сложным вложенным структурам:")
        if ast.body and len(ast.body) > 1:
            if_stmt = ast.body[1]
            if if_stmt.get('branches'):
                print(f"   If statement с {len(if_stmt['branches'])} ветками")
                first_branch = if_stmt['branches'][0]
                if first_branch.get('condition'):
                    condition = first_branch['condition']
                    print(f"   Условие: {condition['type']}")
                    if condition.get('left_operand'):
                        print(f"   Левый операнд: {condition['left_operand']['name']}")
                    if condition.get('right_operand'):
                        print(f"   Правый операнд: {condition['right_operand']['value']}")
        
    except FileNotFoundError:
        print("Файл ast.json не найден. Пропускаем демонстрацию.")


def demo_constructs_loading():
    """Демонстрация загрузки constructs (упрощенная версия)"""
    print("\n" + "=" * 80)
    print("Демонстрация упрощенной загрузки constructs")
    print("=" * 80)
    
    try:
        with open("constructs.yml", "r") as f:
            import yaml
            constructs_data = yaml.safe_load(f)
        
        print("\n1. Загрузка constructs из YAML:")
        print(f"   Найдено {len(constructs_data)} constructs")
        
        # Упрощенный dataclass для constructs
        @dataclass
        class SimpleConstruct(DictLikeDataclass):
            name: str
            kind: Optional[str] = None
            description: Optional[str] = None
            # Используем Any для сложных полей
            actions: Optional[Any] = None
            transitions: Optional[Any] = None
        
        print("\n2. Парсинг constructs с помощью DictLikeDataclass:")
        constructs = {}
        for name, data in constructs_data.items():
            # Создаем упрощенную версию
            construct_data = {"name": name}
            if "kind" in data:
                construct_data["kind"] = data["kind"]
            if "description" in data:
                construct_data["description"] = data["description"]
            
            construct = SimpleConstruct.make(construct_data)
            constructs[name] = construct
            print(f"   Construct '{name}': kind={construct.kind}")
        
        print("\n3. Dict-like доступ к constructs:")
        for name, construct in constructs.items():
            print(f"   {name}: kind={construct['kind']}, description={construct.get('description', 'None')}")
        
        print("\n4. Модификация constructs через dict-доступ:")
        if constructs:
            first_construct = list(constructs.values())[0]
            original_name = first_construct['name']
            first_construct['name'] = f"modified_{original_name}"
            print(f"   Оригинальное имя: {original_name}")
            print(f"   После изменения: {first_construct['name']}")
            print(f"   Синхронизация: {first_construct.name}")
            
            # Восстанавливаем
            first_construct['name'] = original_name
            print(f"   После восстановления: {first_construct['name']}")
        
    except FileNotFoundError:
        print("Файл constructs.yml не найден. Пропускаем демонстрацию.")
    except Exception as e:
        print(f"Ошибка при загрузке constructs: {e}")
        print("Пропускаем демонстрацию constructs.")


def main():
    """Главная функция демонстрации"""
    print("Демонстрация упрощенной загрузки JSON с DictLikeDataclass")
    print("=" * 80)
    
    # Демонстрация загрузки AST
    demo_ast_loading()
    
    # Демонстрация загрузки constructs
    demo_constructs_loading()
    
    print("\n" + "=" * 80)
    print("Преимущества нового подхода:")
    print("=" * 80)
    print("[OK] Убраны все функции _parse_* - код стал намного короче")
    print("[OK] Автоматическая валидация типов и обязательных полей")
    print("[OK] Dict-like доступ к данным: obj['key'] и obj.key")
    print("[OK] Синхронизация между dict и атрибутным доступом")
    print("[OK] Рекурсивное создание вложенных структур")
    print("[OK] Автоматическое преобразование Enum значений")
    print("[OK] Информативные ошибки при неверных данных")
    print("[OK] Поддержка Optional полей")
    print("=" * 80)


if __name__ == "__main__":
    main()
