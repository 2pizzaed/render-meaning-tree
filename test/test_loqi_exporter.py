"""
Тесты для модуля экспорта в loqi-формат.
"""

import os
import tempfile
from src.cfg.loqi_exporter import LoqiExporter
from src.cfg.abstractions import Effects, ActionSpec, ConstructSpec, KindChain, InterruptionType
from src.cfg.cfg import CFG, Node, Edge, Metadata, NodeKind


def test_basic_export():
    """Тест базового экспорта объектов."""
    exporter = LoqiExporter()
    
    # Создаём тестовые объекты
    effect = Effects(interruption_stop=InterruptionType.BREAK)
    action = ActionSpec(role="test_action", kind=KindChain("test.kind"))
    action.effects = [effect]
    
    # Добавляем объекты в экспортер
    exporter.add_object(effect)
    exporter.add_object(action)
    
    # Экспортируем во временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.loqi', delete=False) as f:
        temp_path = f.name
    
    try:
        exporter.write_to_file(temp_path)
        
        # Проверяем, что файл создан и содержит ожидаемое содержимое
        assert os.path.exists(temp_path)
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие объектов
        assert "obj" in content
        assert "Effect" in content
        assert "ActionSpec" in content
        assert "interruption_stop" in content
        assert "role" in content
        
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_cfg_export():
    """Тест экспорта CFG."""
    exporter = LoqiExporter()
    
    # Создаём тестовый CFG
    cfg = CFG("test_cfg")
    
    # Добавляем узел
    metadata = Metadata(assumed_value=True, call_count=1)
    node = cfg.add_node(NodeKind.ATOM, "condition_node", metadata=metadata)
    
    # Добавляем ребро
    edge = cfg.connect(cfg.begin_node, node)
    
    # Экспортируем CFG
    with tempfile.NamedTemporaryFile(mode='w', suffix='.loqi', delete=False) as f:
        temp_path = f.name
    
    try:
        exporter.export_cfg(cfg, temp_path)
        
        # Проверяем, что файл создан
        assert os.path.exists(temp_path)
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие основных элементов CFG
        assert "CFG" in content
        assert "Node" in content
        assert "Edge" in content
        assert "Metadata" in content
        assert "test_cfg" in content
        
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_name_uniqueness():
    """Тест обеспечения уникальности имён объектов."""
    exporter = LoqiExporter()
    
    # Создаём объекты с одинаковыми базовыми именами
    effect1 = Effects(interruption_stop=InterruptionType.BREAK)
    effect2 = Effects(interruption_stop=InterruptionType.BREAK)
    
    exporter.add_object(effect1)
    exporter.add_object(effect2)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.loqi', delete=False) as f:
        temp_path = f.name
    
    try:
        exporter.write_to_file(temp_path)
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Подсчитываем количество объявлений объектов
        obj_declarations = content.count('obj ')
        assert obj_declarations == 2  # Должно быть ровно 2 объекта
        
        # Проверяем, что имена уникальны
        lines = content.split('\n')
        obj_lines = [line for line in lines if line.strip().startswith('obj ')]
        names = [line.split()[1] for line in obj_lines]
        assert len(set(names)) == len(names)  # Все имена должны быть уникальны
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


if __name__ == "__main__":
    test_basic_export()
    test_cfg_export()
    test_name_uniqueness()
    print("Все тесты прошли успешно!")
