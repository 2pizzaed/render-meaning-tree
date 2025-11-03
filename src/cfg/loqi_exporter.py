"""
Loqi Exporter - модуль для экспорта объектов Python в loqi-формат.

Этот модуль предоставляет функциональность для конвертации объектов из 
классов abstractions.py и cfg.py в формат loqi для последующей обработки
алгоритмами проверки.
"""

import builtins
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional, get_origin

from src.cfg.cfg import TraceAct
from src.common_utils import SelfValidatedEnum


class ValueConverter:
    """Конвертер скалярных значений из Python в loqi-формат."""

    @staticmethod
    def convert_value(value: Any, type: type) -> str | None:
        """Конвертирует Python значение в loqi-формат."""
        if value is None:
            return None

        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str) and (value == "true" or value == "false"):
            return value

        if isinstance(value, (int, float)):
            return str(value)

        origin = get_origin(type) or type
        if origin is not Any and isinstance(origin, builtins.type) and issubclass(origin, SelfValidatedEnum):
            assert origin.lookup(value)  # Check if str is a valid enum entry.
            if isinstance(value, str):
                return f"{origin.__name__}:{value}"
            else:
                return f"{origin.__name__}:{value.value}"

        if isinstance(value, str):
            # Экранируем строки, если они содержат специальные символы
            escaped_value = value.replace("\\", "\\\\").replace("\"", "\\\"")
            return f'"{escaped_value}"'

        # Обработка Enum классов
        if (hasattr(value, 'value') and hasattr(value.__class__, '__name__')):
            enum_class_name = value.__class__.__name__
            enum_value = value.value
            return f"{enum_class_name}:{enum_value}"

        # Для других типов возвращаем строковое представление
        return str(value)


class NameRegistry:
    """Реестр имён объектов для обеспечения уникальности объектов в рамках одного типа."""

    def __init__(self):
        self._type_name_to_uname: dict[tuple[str, str], str] = {}

    def register_object(self, obj: Any, preferred_name: str) -> str:
        """Регистрирует объект и возвращает уникальное имя."""
        # Use preferred_name as the key for content-based deduplication
        # If this name already exists, return existing name
        obj_type = type(obj).__name__
        key = (obj_type, preferred_name)

        if key in self._type_name_to_uname:
            # Object of the same type with this name was already registered.
            return self._type_name_to_uname[key]

        # Check for name collision with different type
        if preferred_name in self._type_name_to_uname.values():
            # Name collision with different type - add type prefix
            final_name = f"{obj_type}_{preferred_name}"
            key = (obj_type, final_name)
        else:
            final_name = preferred_name
            # key unchanged.

        # Register the name
        self._type_name_to_uname[key] = final_name
        return final_name

    def get_object_name(self, obj: Any, preferred_name: str) -> str | None:
        """Получает имя объекта, если он зарегистрирован."""
        obj_type = type(obj).__name__
        key = (obj_type, preferred_name)
        return self._type_name_to_uname.get(key)

class ExporterManager:
    """Вспомогательный класс для управления "экспортерами" -- подклассами ObjectExporter."""
    registered_classes: dict[str, type['ObjectExporter']] = {}

    @classmethod
    def register_class(cls, class_type: type['ObjectExporter']) -> type:
        cls.registered_classes[class_type.__name__] = class_type
        return class_type

    def __init__(self, name_registry: NameRegistry | None = None, exporters: dict[type, 'ObjectExporter'] | None = None):
        self.name_registry = name_registry or NameRegistry()
        self.exporters = exporters or {}

    def get_exporter_for(self, obj: Any) -> Optional['ObjectExporter']:
        if self.exporters and type(obj) in self.exporters:
            return self.exporters[type(obj)]
        return None

    def get_registered_name_for_object(self, obj: Any) -> str | None:
        """Получить зарегистрированное имя для связанного объекта (если есть экспортер для его типа)."""
        exporter = self.get_exporter_for(obj)
        if exporter:
            return exporter.register_object(obj)
        return None


class ObjectExporter(ExporterManager, ABC):
    """Абстрактный базовый класс для экспортеров конкретных типов объектов."""

    def __init__(self, name_registry: NameRegistry | None = None, exporters: dict[type, 'ObjectExporter'] | None = None):
        super().__init__(name_registry, exporters)

    @abstractmethod
    def get_supported_types(self) -> list[type]:
        """ Для каких типов экспортируемых объектов предназначен "экспортёр". """
        raise NotImplementedError

    @abstractmethod
    def get_preferred_name(self, obj: Any) -> str:
        """Получить предпочтительное имя объекта на основе его свойств."""
        pass

    @abstractmethod
    def get_class_name(self, obj: Any) -> str:
        """Получить имя класса (типа) объекта."""
        pass

    def is_object_registered(self, obj: Any) -> bool:
        """Был ли объект зарегистрирован."""
        preferred_name = self.get_preferred_name(obj)
        return self.name_registry.get_object_name(obj, preferred_name) is not None

    def register_object(self, obj: Any) -> str:
        """Получить зарегистрированное уникальное имя объекта."""
        preferred_name = self.get_preferred_name(obj)
        return self.name_registry.register_object(obj, preferred_name)

    @abstractmethod
    def export_properties(self, obj: Any) -> dict[str, Any]:
        """Получить скалярные свойства объекта."""
        pass

    @abstractmethod
    def export_relationships(self, obj: Any) -> dict[str, list[Any]]:
        """Получить отношения (ссылки на другие объекты). Возвращает объекты, а не их имена."""
        pass

    def export_object(self, obj: Any) -> str:
        """Экспортирует объект в loqi-формат."""
        name = self.register_object(obj)
        class_name = self.get_class_name(obj)
        properties = self.export_properties(obj)
        relationships = self.export_relationships(obj)

        lines = [f"obj {name} : {class_name} {{"]

        # Добавляем свойства
        for prop_name, prop_value in properties.items():
            converted_value = ValueConverter.convert_value(prop_value, obj.__class__.__annotations__.get(prop_name, Any))
            if converted_value is not None:
                lines.append(f"  {prop_name} = {converted_value};")

        # Добавляем отношения: преобразуем объекты в их имена
        for rel_name, rel_objects in relationships.items():
            for rel_obj in rel_objects:
                if rel_obj is None:
                    continue
                # Получаем имя зарегистрированного объекта
                obj_name = self.get_registered_name_for_object(rel_obj)
                if obj_name:
                    lines.append(f"  {rel_name}({obj_name});")

        lines.append("}")
        return "\n".join(lines)


class LoqiExporter(ExporterManager):
    """Главный класс-координатор экспорта объектов в loqi-формат."""

    def __init__(self):
        super().__init__()
        self.exported_objects: list[Any] = []
        self.vars: dict[Any, str] = {}
        self._setup_exporters()

    def _setup_exporters(self):
        """Настраивает экспортеры для всех поддерживаемых типов."""
        # Регистрируем экспортеры: создаём объекты зарегистрированных классов
        try:
            # this triggers whole file to run thus registering all defined classes.
            from .loqi_exporters import CFGExporter
        except ImportError as e:
            # Если импорт не удался, оставляем пустой список экспортеров
            print(f"Warning: Could not import exporters: {e}")
            return

        exporters = self.registered_classes.values()

        for exporter_class in exporters:
            exporter = exporter_class(self.name_registry, self.exporters)
            for obj_type in exporter.get_supported_types():
                self.exporters[obj_type] = exporter

    def lookup_object(self, name: str) -> Any | None:
        for obj in self.exported_objects:
            registered_name = self.get_registered_name_for_object(obj)
            if registered_name == name:
                return obj
        return None

    def set_var(self, name: str, obj: str | Any) -> None:
        if isinstance(obj, str) and self.lookup_object(obj):
            self.vars[obj] = name
        elif exporter := self.get_exporter_for(obj):
            self.vars[exporter.register_object(obj)] = name
        else:
            raise ValueError(f"Object with name `{obj}` not found among exported objects.")

    def add_trace(self, trace: list[TraceAct]) -> None:
        """Добавляет трассировку для экспорта."""
        exporter: 'TraceActExporter' = self.exporters.get(type(trace[0]))

        if exporter:
            exporter.add_full_trace(trace) # pyright: ignore[reportAttributeAccessIssue]

        for trace_act in trace:
            if not exporter.is_object_registered(trace_act): # pyright: ignore[reportOptionalMemberAccess]
                exporter.register_object(trace_act) # pyright: ignore[reportOptionalMemberAccess]
                self.exported_objects.append(trace_act)
                # Автоматически регистрируем связанные объекты (рекурсивно)
                self._add_related_objects(trace_act, True)

    def add_paths(self, paths: list['PathInfo']) -> None:
        """Добавляет пути PathInfo для экспорта."""
        from .reachability import PathInfo
        
        if not paths:
            return
        
        exporter: 'PathInfoExporter' = self.exporters.get(PathInfo)

        if exporter:
            exporter.add_all_paths(paths) # pyright: ignore[reportAttributeAccessIssue]

        for path_info in paths:
            if not exporter.is_object_registered(path_info): # pyright: ignore[reportOptionalMemberAccess]
                exporter.register_object(path_info) # pyright: ignore[reportOptionalMemberAccess]
                self.exported_objects.append(path_info)
                # Автоматически регистрируем связанные объекты (рекурсивно)
                self._add_related_objects(path_info, True)

    def add_object(self, obj: Any):
        """Добавляет объект для экспорта, игнорируя дубликаты."""
        from .reachability import PathInfo

        if isinstance(obj, PathInfo):
            raise ValueError("PathInfo objects should be added via `add_paths` method.")
        if obj is None:
            return

        exporter = self.exporters.get(type(obj))
        if not exporter:
            return
        if not exporter.is_object_registered(obj):
            # not yet registered.
            exporter.register_object(obj)
            self.exported_objects.append(obj)
            # Автоматически регистрируем связанные объекты (рекурсивно)
            self._add_related_objects(obj)
        elif 0:
            # debugging. TODO: remove this print.
            print(f"Warning: Object `{exporter.get_registered_name_for_object(obj)}` already registered, ignoring.")

    def _add_related_objects(self, obj: Any, ignore_self_type: bool = False):
        """Добавляет все объекты, связанные с данным объектом через relationships."""
        exporter = self.get_exporter_for(obj)
        if not exporter:
            return

        # Получаем relationships - теперь это объекты, а не имена
        relationships = exporter.export_relationships(obj)

        # Проходим по всем связанным объектам и добавляем их
        for rel_name, rel_objects in relationships.items():
            for rel_obj in rel_objects:
                if ignore_self_type and type(rel_obj) is type(obj):
                    continue
                if rel_obj is not None:
                    # Рекурсивный вызов add_object - он сам проверит на дубликаты
                    self.add_object(rel_obj)

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
        # Добавляем сам CFG (и все связанные с ним объекты рекурсивно)
        self.add_object(cfg)

    def _register_all_objects(self):
        """Регистрирует все объекты и их имена."""
        for obj in self.exported_objects:
            exporter = self.get_exporter_for(obj)
            if exporter:
                exporter.register_object(obj)  # Это зарегистрирует имя

    def get_exporter_for(self, obj: Any) -> ObjectExporter | None:
        if type(obj) in self.exporters:
            return self.exporters[type(obj)]
        return None

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
                        if var := self.vars.get(self.name_registry.get_object_name(obj, exporter.get_preferred_name(obj))):
                            var = var if " " not in var else f"`{var}`"
                            loqi_code = f"var {var} = {loqi_code}"
                        f.write(loqi_code)
                        f.write("\n\n")
