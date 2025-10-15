#!/usr/bin/env python3
"""
Тест модуля визуализации CFG.

Тестирует функциональность визуализации графов потока управления
с использованием NetworkX и matplotlib.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.cfg.cfg_visualizer import visualize_cfg, _create_node_label, _create_edge_label, _build_networkx_graph
from src.cfg.cfg_builder import CFGBuilder
from src.cfg.abstractions import load_constructs, Constraints
from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.cfg import CFG, BEGIN, END, Metadata


class TestCFGVisualizer(unittest.TestCase):
    """Тесты для модуля визуализации CFG."""
    
    @classmethod
    def setUpClass(cls):
        """Настройка для всех тестов класса."""
        cls.constructs = load_constructs()
        cls.builder = CFGBuilder(cls.constructs)
    
    def setUp(self):
        """Настройка для каждого теста."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Очистка после каждого теста."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def create_example_ast(self):
        """Создаёт пример AST для тестирования.
        
        Тот же AST, который использовался для создания example_cfg.png
        """
        return {
            "type": "program_entry_point",
            "id": 1,
            "body": [
                {
                    "type": "if_statement", 
                    "id": 2,
                    "branches": [
                        {
                            "type": "if_branch",
                            "condition": {"type": "condition", "id": 3},
                            "body": {
                                "type": "compound_statement",
                                "id": 4,
                                "statements": [
                                    {"type": "assignment_statement", "id": 5}
                                ]
                            }
                        }
                    ],
                    "elseBranch": {
                        "type": "compound_statement",
                        "id": 6,
                        "statements": [
                            {"type": "assignment_statement", "id": 7}
                        ]
                    }
                }
            ]
        }
    
    def test_create_node_label(self):
        """Тест создания меток для узлов."""
        # Тест BEGIN узла
        begin_node = CFG("test").begin_node
        label = _create_node_label(begin_node)
        self.assertIn("BEGIN", label)
        
        # Тест END узла
        end_node = CFG("test").end_node
        label = _create_node_label(end_node)
        self.assertIn("END", label)
        
        # Тест обычного узла
        cfg = CFG("test")
        node = cfg.add_node("condition", "cond", Metadata())
        label = _create_node_label(node)
        self.assertIn("condition", label)
        self.assertIn("cond", label)
    
    def test_create_edge_label(self):
        """Тест создания меток для рёбер."""
        # Тест ребра без constraints
        cfg = CFG("test")
        edge = cfg.connect(cfg.begin_node, cfg.end_node)
        label = _create_edge_label(edge)
        self.assertEqual(label, "")
        
        # Тест ребра с condition_value = True
        true_constraint = Constraints(condition_value=True)
        edge = cfg.connect(cfg.begin_node, cfg.end_node, constraints=true_constraint)
        label = _create_edge_label(edge)
        self.assertIn("T", label)
        
        # Тест ребра с condition_value = False
        false_constraint = Constraints(condition_value=False)
        edge = cfg.connect(cfg.begin_node, cfg.end_node, constraints=false_constraint)
        label = _create_edge_label(edge)
        self.assertIn("F", label)
    
    def test_build_networkx_graph(self):
        """Тест конвертации CFG в NetworkX граф."""
        cfg = CFG("test")
        node1 = cfg.add_node("condition", "cond")
        node2 = cfg.add_node("compound", "body")
        
        # Добавляем рёбра с constraints
        true_constraint = Constraints(condition_value=True)
        cfg.connect(cfg.begin_node, node1, constraints=true_constraint)
        cfg.connect(node1, node2)
        cfg.connect(node2, cfg.end_node)
        
        # Конвертируем в NetworkX
        G = _build_networkx_graph(cfg)
        
        # Проверяем узлы
        self.assertEqual(len(G.nodes()), len(cfg.nodes))
        self.assertIn(cfg.begin_node.id, G.nodes())
        self.assertIn(cfg.end_node.id, G.nodes())
        self.assertIn(node1.id, G.nodes())
        self.assertIn(node2.id, G.nodes())
        
        # Проверяем рёбра
        self.assertEqual(len(G.edges()), len(cfg.edges))
        self.assertTrue(G.has_edge(cfg.begin_node.id, node1.id))
        self.assertTrue(G.has_edge(node1.id, node2.id))
        self.assertTrue(G.has_edge(node2.id, cfg.end_node.id))
        
        # Проверяем метки
        self.assertIn("T", G[cfg.begin_node.id][node1.id]['label'])
    
    def test_visualize_cfg_basic(self):
        """Тест базовой визуализации CFG."""
        cfg = CFG("test_basic")
        output_file = os.path.join(self.temp_dir, "test_basic.png")
        
        result = visualize_cfg(cfg, output_file)
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))
        self.assertGreater(os.path.getsize(output_file), 1000)  # Проверяем, что файл не пустой
    
    def test_visualize_cfg_with_constraints(self):
        """Тест визуализации CFG с constraints."""
        cfg = CFG("test_constraints")
        
        # Создаём узлы
        node1 = cfg.add_node("condition", "cond")
        node2 = cfg.add_node("compound", "body")
        
        # Создаём рёбра с constraints
        true_constraint = Constraints(condition_value=True)
        false_constraint = Constraints(condition_value=False)
        
        cfg.connect(cfg.begin_node, node1, constraints=true_constraint)
        cfg.connect(node1, node2, constraints=false_constraint)
        cfg.connect(node2, cfg.end_node)
        
        output_file = os.path.join(self.temp_dir, "test_constraints.png")
        result = visualize_cfg(cfg, output_file)
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))
    
    def test_visualize_cfg_from_ast(self):
        """Тест визуализации CFG, созданного из AST.
        
        Воспроизводит процесс создания example_cfg.png
        """
        # Создаём AST
        ast_data = self.create_example_ast()
        
        # Создаём CFG из AST
        wrapped_ast = ASTNodeWrapper(ast_node=ast_data)
        cfg = self.builder.make_cfg_for_ast(wrapped_ast)
        
        self.assertIsNotNone(cfg, "CFG должен быть создан")
        
        # Визуализируем
        output_file = os.path.join(self.temp_dir, "test_from_ast.png")
        result = visualize_cfg(cfg, output_file, figsize=(14, 10))
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))
        
        # Проверяем размер файла (должен быть достаточно большим)
        file_size = os.path.getsize(output_file)
        self.assertGreater(file_size, 100000, "Файл визуализации должен быть достаточно большим")
        
        print(f"\nCFG создан: {cfg.name}")
        print(f"Узлов: {len(cfg.nodes)}")
        print(f"Рёбер: {len(cfg.edges)}")
        print(f"Визуализация сохранена: {output_file}")
        print(f"Размер файла: {file_size} байт")
    
    def test_visualize_cfg_different_layouts(self):
        """Тест визуализации с разными layout."""
        cfg = CFG("test_layouts")
        node = cfg.add_node("condition", "cond")
        cfg.connect(cfg.begin_node, node)
        cfg.connect(node, cfg.end_node)
        
        # Тест spring layout
        output_file_spring = os.path.join(self.temp_dir, "test_spring.png")
        result_spring = visualize_cfg(cfg, output_file_spring, layout="spring")
        self.assertTrue(os.path.exists(result_spring))
        
        # Тест hierarchical layout
        output_file_hier = os.path.join(self.temp_dir, "test_hierarchical.png")
        result_hier = visualize_cfg(cfg, output_file_hier, layout="hierarchical")
        self.assertTrue(os.path.exists(result_hier))
    
    def test_visualize_empty_cfg(self):
        """Тест визуализации пустого CFG."""
        cfg = CFG("empty")
        output_file = os.path.join(self.temp_dir, "test_empty.png")
        
        result = visualize_cfg(cfg, output_file)
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))
    
    def test_visualize_cfg_large(self):
        """Тест визуализации большого CFG."""
        cfg = CFG("test_large")
        
        # Создаём много узлов
        nodes = []
        for i in range(10):
            node = cfg.add_node(f"node_{i}", f"role_{i}")
            nodes.append(node)
        
        # Создаём сложную структуру рёбер
        cfg.connect(cfg.begin_node, nodes[0])
        for i in range(len(nodes) - 1):
            cfg.connect(nodes[i], nodes[i + 1])
        cfg.connect(nodes[-1], cfg.end_node)
        
        # Добавляем дополнительные рёбра для сложности
        cfg.connect(nodes[0], nodes[5])
        cfg.connect(nodes[3], nodes[8])
        
        output_file = os.path.join(self.temp_dir, "test_large.png")
        result = visualize_cfg(cfg, output_file, figsize=(16, 12))
        
        self.assertEqual(result, output_file)
        self.assertTrue(os.path.exists(output_file))
        
        file_size = os.path.getsize(output_file)
        self.assertGreater(file_size, 50000, "Файл большого CFG должен быть достаточно большим")


def main():
    """Запуск тестов с подробным выводом."""
    print("=== ТЕСТЫ МОДУЛЯ ВИЗУАЛИЗАЦИИ CFG ===")
    print()
    
    # Создаём тестовый класс
    test_instance = TestCFGVisualizer()
    test_instance.setUpClass()
    
    # Запускаем основные тесты
    tests_to_run = [
        ("Создание меток узлов", test_instance.test_create_node_label),
        ("Создание меток рёбер", test_instance.test_create_edge_label),
        ("Конвертация в NetworkX", test_instance.test_build_networkx_graph),
        ("Базовая визуализация", test_instance.test_visualize_cfg_basic),
        ("Визуализация с constraints", test_instance.test_visualize_cfg_with_constraints),
        ("Визуализация из AST", test_instance.test_visualize_cfg_from_ast),
        ("Разные layout", test_instance.test_visualize_cfg_different_layouts),
        ("Пустой CFG", test_instance.test_visualize_empty_cfg),
        ("Большой CFG", test_instance.test_visualize_cfg_large),
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
        print("УСПЕХ: ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return 0
    else:
        print("ОШИБКА: ЕСТЬ ПРОВАЛЕННЫЕ ТЕСТЫ")
        return 1


if __name__ == "__main__":
    exit(main())
