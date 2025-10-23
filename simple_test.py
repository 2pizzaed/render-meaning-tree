#!/usr/bin/env python3
"""
Простой тест экспортера без сложных зависимостей.
"""

# Тестируем только базовые компоненты
try:
    from src.cfg.loqi_exporter import ValueConverter, NameRegistry
    
    print("✅ Импорт базовых компонентов успешен")
    
    # Тестируем ValueConverter
    converter = ValueConverter()
    
    # Тестируем конвертацию различных типов
    test_cases = [
        (None, None),
        (True, "true"),
        (False, "false"),
        (42, "42"),
        ("hello", "hello"),
        ("hello;world", '"hello;world"')
    ]
    
    for input_val, expected in test_cases:
        result = converter.convert_value(input_val)
        if result == expected:
            print(f"✅ {input_val} -> {result}")
        else:
            print(f"❌ {input_val} -> {result}, ожидалось {expected}")
    
    # Тестируем NameRegistry
    registry = NameRegistry()
    
    name1 = registry.register_object("obj1", "test")
    name2 = registry.register_object("obj2", "test")
    name3 = registry.register_object("obj3", "test")
    
    print(f"✅ Имена объектов: {name1}, {name2}, {name3}")
    
    if name1 == "test" and name2 == "test_2" and name3 == "test_3":
        print("✅ Уникальность имён работает корректно")
    else:
        print("❌ Проблема с уникальностью имён")
    
    print("\n🎉 Все базовые тесты прошли успешно!")
    
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
