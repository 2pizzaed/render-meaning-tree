#!/usr/bin/env python3
"""
Пример использования loqi экспортера.
"""

import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_sample_cfg():
    """Создаёт пример CFG для демонстрации."""
    from src.cfg.cfg import CFG, NodeKind
    from src.cfg.abstractions import Effects, InterruptionType
    
    # Создаём CFG
    cfg = CFG("sample_cfg")
    
    # Создаём эффект
    effect = Effects(interruption_stop=InterruptionType.BREAK)
    
    # Создаём узел с эффектом
    node = cfg.add_node(NodeKind.CONDITION, "sample_node")
    node.effects = [effect]
    
    # Создаём ребро
    edge = cfg.connect(cfg.begin_node, node)
    
    return cfg

def main():
    """Основная функция."""
    try:
        print("Создание примера CFG...")
        cfg = create_sample_cfg()
        
        print("Создание экспортера...")
        from src.cfg.loqi_exporter import LoqiExporter
        exporter = LoqiExporter()
        
        print("Экспорт CFG...")
        output_file = "example_output.loqi"
        exporter.export_cfg(cfg, output_file)
        
        print(f"✅ CFG экспортирован в файл: {output_file}")
        
        # Показываем содержимое файла
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            print("\nСодержимое файла:")
            print("-" * 50)
            print(content)
            print("-" * 50)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
