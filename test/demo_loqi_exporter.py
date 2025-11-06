#!/usr/bin/env python3
"""
Демонстрация работы loqi экспортера.
"""

import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)))

from src.cfg.loqi_exporter import LoqiExporter
from src.cfg.abstractions import Effects, ActionSpec, ConstructSpec, KindChain, InterruptionType
from src.cfg.cfg import CFG, Node, Edge, Metadata, NodeKind


def demo_basic_export():
    """Демонстрация базового экспорта объектов."""
    print("=== Демонстрация базового экспорта ===")
    
    exporter = LoqiExporter()
    
    # Создаём тестовые объекты
    effect = Effects(interruption_stop=InterruptionType.BREAK)
    action = ActionSpec(role="test_action", kind=KindChain("test.kind"))
    action.effects = [effect]
    
    # Добавляем объекты в экспортер
    exporter.add_object(effect)
    exporter.add_object(action)
    
    # Экспортируем в файл
    output_file = "test/output/demo_export.loqi"
    exporter.write_to_file(output_file)
    
    print(f"Объекты экспортированы в файл: {output_file}")
    
    # Показываем содержимое файла
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print("\nСодержимое файла:")
        print("-" * 50)
        print(content)
        print("-" * 50)


def demo_cfg_export():
    """Демонстрация экспорта CFG."""
    print("\n=== Демонстрация экспорта CFG ===")
    
    exporter = LoqiExporter()
    
    # Создаём тестовый CFG
    cfg = CFG("demo_cfg")
    
    # Добавляем узел
    metadata = Metadata(assumed_value=True, call_count=1)
    node = cfg.add_node(NodeKind.CONDITION, "condition_node", metadata=metadata)

    # Создаём эффект
    effect = Effects(interruption_stop=InterruptionType.BREAK)
    node.effects = [effect]

    # Добавляем ребро
    edge = cfg.connect(cfg.begin_node, node)
    
    # Экспортируем CFG
    output_file = "test/output/demo_cfg_export.loqi"
    exporter.export_cfg(cfg, output_file)
    
    print(f"CFG экспортирован в файл: {output_file}")
    
    # Показываем содержимое файла
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print("\nСодержимое файла:")
        print("-" * 50)
        print(content)
        print("-" * 50)


def main():
    """Основная функция демонстрации."""
    try:
        demo_basic_export()
        demo_cfg_export()
        print("\n✅ Все демонстрации выполнены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении демонстрации: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
