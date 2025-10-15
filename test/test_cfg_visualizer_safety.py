#!/usr/bin/env python3
"""
Тест безопасности визуализации CFG.

Тестирует обработку неполных и повреждённых графов потока управления.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.cfg.cfg_visualizer import visualize_cfg, diagnose_cfg, _build_networkx_graph
from src.cfg.cfg import CFG, BEGIN, END, Metadata
from src.cfg.abstractions import Constraints


class TestCFGVisualizerSafety(unittest.TestCase):
    """Тесты безопасности визуализации CFG."""
    
    def setUp(self):
        """Настройка для каждого теста."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Очистка после каждого теста."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_orphan_edges(self):
        """Тест обработки висячих рёбер."""
        cfg = CFG("test_orphan")
        
        # Создаём узлы
        node1 = cfg.add_node("condition", "cond")
        node2 = cfg.add_node("compound", "body")
        
        # Создаём висячие рёбра (ссылаются на несуществующие узлы)
        cfg.edges.append(type('Edge', (), {
            'src': 'nonexistent_src',
            'dst': node1.id,
            'constraints': None
        })())
        
        cfg.edges.append(type('Edge', (), {
            'src': node1.id,
            'dst': 'nonexistent_dst',
            'constraints': None
        })())
        
        # Нормальное ребро
        cfg.connect(node1, node2)
        
        # Диагностика
        issues = diagnose_cfg(cfg)
        self.assertEqual(len(issues['orphan_edges']), 2)
        self.assertIn('nonexistent_src', issues['missing_nodes'])
        self.assertIn('nonexistent_dst', issues['missing_nodes'])
        
        # Визуализация должна работать
        output_file = os.path.join(self.temp_dir, "test_orphan.png")
        result = visualize_cfg(cfg, output_file)
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))
    
    def test_empty_cfg(self):
        """Тест обработки пустого CFG."""
        cfg = CFG("empty")
        
        # Диагностика
        issues = diagnose_cfg(cfg)
        self.assertEqual(issues['total_nodes'], 2)  # BEGIN и END
        self.assertEqual(issues['total_edges'], 0)
        
        # Визуализация должна работать
        output_file = os.path.join(self.temp_dir, "test_empty.png")
        result = visualize_cfg(cfg, output_file)
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))
    
    def test_disconnected_nodes(self):
        """Тест обработки отключённых узлов."""
        cfg = CFG("test_disconnected")
        
        # Создаём узлы без рёбер между ними
        node1 = cfg.add_node("condition", "cond")
        node2 = cfg.add_node("compound", "body")
        
        # Диагностика
        issues = diagnose_cfg(cfg)
        self.assertGreater(len(issues['disconnected_nodes']), 0)
        
        # Визуализация должна работать
        output_file = os.path.join(self.temp_dir, "test_disconnected.png")
        result = visualize_cfg(cfg, output_file)
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))
    
    def test_networkx_graph_building_safety(self):
        """Тест безопасного построения NetworkX графа."""
        cfg = CFG("test_networkx")
        
        # Создаём узлы
        node1 = cfg.add_node("condition", "cond")
        node2 = cfg.add_node("compound", "body")
        
        # Добавляем висячие рёбра
        cfg.edges.append(type('Edge', (), {
            'src': 'missing_src',
            'dst': node1.id,
            'constraints': None
        })())
        
        # Строим NetworkX граф
        G = _build_networkx_graph(cfg)
        
        # Проверяем, что висячие рёбра не добавлены
        self.assertFalse(G.has_edge('missing_src', node1.id))
        
        # Проверяем, что нормальные рёбра добавлены (если они есть)
        # В данном тесте мы не добавляем нормальные рёбра, только висячие
        self.assertEqual(len(G.edges()), 0)  # Только висячие рёбра, которые пропускаются
    
    def test_malformed_cfg_data(self):
        """Тест обработки повреждённых данных CFG."""
        cfg = CFG("test_malformed")
        
        # Создаём узел с отсутствующими полями
        node = cfg.add_node("condition", "cond")
        
        # Повреждаем данные узла
        node.metadata = None
        node.kind = None
        
        # Визуализация должна работать
        output_file = os.path.join(self.temp_dir, "test_malformed.png")
        result = visualize_cfg(cfg, output_file)
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))
    
    def test_large_orphan_edges(self):
        """Тест обработки большого количества висячих рёбер."""
        cfg = CFG("test_large_orphan")
        
        # Создаём много висячих рёбер
        for i in range(100):
            cfg.edges.append(type('Edge', (), {
                'src': f'missing_src_{i}',
                'dst': f'missing_dst_{i}',
                'constraints': None
            })())
        
        # Диагностика
        issues = diagnose_cfg(cfg)
        # Каждое висячее ребро создаёт две записи (missing src и missing dst)
        self.assertEqual(len(issues['orphan_edges']), 200)
        
        # Визуализация должна работать
        output_file = os.path.join(self.temp_dir, "test_large_orphan.png")
        result = visualize_cfg(cfg, output_file)
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))


def main():
    """Запуск тестов безопасности с подробным выводом."""
    print("=== ТЕСТЫ БЕЗОПАСНОСТИ ВИЗУАЛИЗАЦИИ CFG ===")
    print()
    
    # Создаём тестовый класс
    test_instance = TestCFGVisualizerSafety()
    
    # Запускаем тесты безопасности
    tests_to_run = [
        ("Висячие рёбра", test_instance.test_orphan_edges),
        ("Пустой CFG", test_instance.test_empty_cfg),
        ("Отключённые узлы", test_instance.test_disconnected_nodes),
        ("Безопасное построение NetworkX", test_instance.test_networkx_graph_building_safety),
        ("Повреждённые данные CFG", test_instance.test_malformed_cfg_data),
        ("Много висячих рёбер", test_instance.test_large_orphan_edges),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_method in tests_to_run:
        try:
            print(f"Тест: {test_name}...")
            test_instance.setUp()
            test_method()
            print(f"OK {test_name} - ПРОЙДЕН")
            passed += 1
        except Exception as e:
            print(f"FAIL {test_name} - ПРОВАЛЕН: {e}")
            failed += 1
        finally:
            test_instance.tearDown()
        print()
    
    print(f"=== РЕЗУЛЬТАТЫ ===")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {failed}")
    print(f"Всего: {passed + failed}")
    
    if failed == 0:
        print("УСПЕХ: ВСЕ ТЕСТЫ БЕЗОПАСНОСТИ ПРОЙДЕНЫ!")
        return 0
    else:
        print("ОШИБКА: ЕСТЬ ПРОВАЛЕННЫЕ ТЕСТЫ БЕЗОПАСНОСТИ")
        return 1


if __name__ == "__main__":
    exit(main())
