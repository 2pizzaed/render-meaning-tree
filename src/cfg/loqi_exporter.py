"""
Loqi Exporter - модуль для экспорта объектов Python в loqi-формат.

Этот модуль предоставляет функциональность для конвертации объектов из 
классов abstractions.py и cfg.py в формат loqi для последующей обработки
алгоритмами проверки.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
import re


class ValueConverter:
    """Конвертер скалярных значений из Python в loqi-формат."""
    
    @staticmethod
    def convert_value(value: Any) -> Optional[str]:
        """Конвертирует Python значение в loqi-формат."""
        if value is None:
            return None
        
        if isinstance(value, bool):
            return "true" if value else "false"
        
        if isinstance(value, (int, float)):
            return str(value)
        
        if isinstance(value, str):
            # Экранируем строки, если они содержат специальные символы
            if any(char in value for char in ['"', "'", ';', '{', '}', '(', ')']):
                return f'"{value}"'
            return value
        
        # Обработка Enum классов
        if hasattr(value, 'value') and hasattr(value.__class__, '__name__'):
            enum_class_name = value.__class__.__name__
            enum_value = value.value
            # Преобразуем enum значение в нижний регистр для соответствия loqi
            if isinstance(enum_value, str):
                enum_value = enum_value.lower()
            return f"{enum_class_name}:{enum_value}"
        
        # Для других типов возвращаем строковое представление
        return str(value)


class NameRegistry:
    """Реестр имён объектов для обеспечения уникальности."""
    
    def __init__(self):
        self._used_names: Set[str] = set()
        self._object_to_name: Dict[Any, str] = {}
    
    def register_object(self, obj: Any, preferred_name: str) -> str:
        """Регистрирует объект и возвращает уникальное имя."""
        unique_name = self._make_unique_name(preferred_name)
        self._used_names.add(unique_name)
        self._object_to_name[obj] = unique_name
        return unique_name
    
    def get_object_name(self, obj: Any) -> Optional[str]:
        """Получает имя объекта, если он зарегистрирован."""
        return self._object_to_name.get(obj)
    
    def _make_unique_name(self, base_name: str) -> str:
        """Создаёт уникальное имя на основе базового."""
        # Очищаем имя от недопустимых символов
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', base_name)
        if not clean_name or clean_name[0].isdigit():
            clean_name = f"obj_{clean_name}"
        
        if clean_name not in self._used_names:
            return clean_name
        
        # Добавляем суффикс для уникальности
        counter = 1
        while f"{clean_name}_{counter}" in self._used_names:
            counter += 1
        
        return f"{clean_name}_{counter}"


class ObjectExporter(ABC):
    """Абстрактный базовый класс для экспортеров конкретных типов объектов."""
    
    def __init__(self, name_registry: NameRegistry):
        self.name_registry = name_registry
    
    @abstractmethod
    def get_object_name(self, obj: Any) -> str:
        """Получить уникальное имя объекта."""
        pass
    
    @abstractmethod
    def get_class_name(self, obj: Any) -> str:
        """Получить имя класса (типа) объекта."""
        pass
    
    @abstractmethod
    def export_properties(self, obj: Any) -> Dict[str, Any]:
        """Получить скалярные свойства объекта."""
        pass
    
    @abstractmethod
    def export_relationships(self, obj: Any) -> Dict[str, List[str]]:
        """Получить отношения (ссылки на другие объекты)."""
        pass
    
    def export_object(self, obj: Any) -> str:
        """Экспортирует объект в loqi-формат."""
        name = self.get_object_name(obj)
        class_name = self.get_class_name(obj)
        properties = self.export_properties(obj)
        relationships = self.export_relationships(obj)
        
        lines = [f"obj {name} : {class_name} {{"]
        
        # Добавляем свойства
        for prop_name, prop_value in properties.items():
            converted_value = ValueConverter.convert_value(prop_value)
            if converted_value is not None:
                lines.append(f"    {prop_name} = {converted_value};")
        
        # Добавляем отношения
        for rel_name, rel_objects in relationships.items():
            for obj_name in rel_objects:
                lines.append(f"    {rel_name}({obj_name});")
        
        lines.append("}")
        return "\n".join(lines)


class LoqiExporter:
    """Главный класс-координатор экспорта объектов в loqi-формат."""
    
    def __init__(self):
        self.name_registry = NameRegistry()
        self.exporters: Dict[type, ObjectExporter] = {}
        self.exported_objects: List[Any] = []
        self._setup_exporters()
    
    def _setup_exporters(self):
        """Настраивает экспортеры для всех поддерживаемых типов."""
        # Импортируем экспортеры здесь, чтобы избежать циклических импортов
        try:
            from .loqi_exporters import (
                EffectsExporter, IdentificationExporter, BehaviourExporter,
                ConstraintsExporter, ActionSpecExporter, TransitionSpecExporter,
                ConstructSpecExporter, MetadataExporter, NodeExporter,
                EdgeExporter, CFGExporter
            )
        except ImportError as e:
            # Если импорт не удался, создаём пустой список экспортеров
            print(f"Warning: Could not import exporters: {e}")
            return
        
        # Регистрируем экспортеры
        exporters = [
            EffectsExporter, IdentificationExporter, BehaviourExporter,
            ConstraintsExporter, ActionSpecExporter, TransitionSpecExporter,
            ConstructSpecExporter, MetadataExporter, NodeExporter,
            EdgeExporter, CFGExporter
        ]
        
        for exporter_class in exporters:
            exporter = exporter_class(self.name_registry)
            for obj_type in exporter.get_supported_types():
                self.exporters[obj_type] = exporter
    
    def add_object(self, obj: Any):
        """Добавляет объект для экспорта."""
        if obj is not None and type(obj) in self.exporters:
            self.exported_objects.append(obj)
    
    def export_cfg(self, cfg, output_path: str):
        """Экспортирует CFG и все связанные объекты в файл."""
        # Собираем все объекты из CFG
        self._collect_cfg_objects(cfg)
        
        # Выполняем двухпроходный экспорт
        self._register_all_objects()
        self._write_to_file(output_path)
    
    def write_to_file(self, output_path: str):
        """Записывает все добавленные объекты в файл."""
        self._register_all_objects()
        self._write_to_file(output_path)
    
    def _collect_cfg_objects(self, cfg):
        """Собирает все объекты из CFG для экспорта."""
        # Добавляем сам CFG
        self.add_object(cfg)
        
        # Добавляем все узлы и их метаданные
        for node in cfg.nodes.values():
            self.add_object(node)
            if hasattr(node, 'metadata') and node.metadata:
                self.add_object(node.metadata)
        
        # Добавляем все рёбра и их метаданные
        for edge in cfg.edges:
            self.add_object(edge)
            if hasattr(edge, 'metadata') and edge.metadata:
                self.add_object(edge.metadata)
    
    def _register_all_objects(self):
        """Регистрирует все объекты и их имена."""
        for obj in self.exported_objects:
            if type(obj) in self.exporters:
                exporter = self.exporters[type(obj)]
                exporter.get_object_name(obj)  # Это зарегистрирует имя
    
    def _write_to_file(self, output_path: str):
        """Записывает экспортированные объекты в файл."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("// Экспортированные объекты из Python\n\n")
            
            # Группируем объекты по типу для лучшей читаемости
            objects_by_type = {}
            for obj in self.exported_objects:
                obj_type = type(obj)
                if obj_type in self.exporters:
                    if obj_type not in objects_by_type:
                        objects_by_type[obj_type] = []
                    objects_by_type[obj_type].append(obj)
            
            # Экспортируем объекты по типам
            for obj_type, objects in objects_by_type.items():
                if objects:  # Проверяем, что есть объекты этого типа
                    f.write(f"// {obj_type.__name__} objects\n")
                    for obj in objects:
                        exporter = self.exporters[obj_type]
                        loqi_code = exporter.export_object(obj)
                        f.write(loqi_code)
                        f.write("\n\n")
