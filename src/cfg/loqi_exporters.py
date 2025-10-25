"""
Конкретные экспортеры для каждого типа объектов из abstractions.py и cfg.py.
"""

from typing import Any, Dict, List, Type
from .loqi_exporter import ObjectExporter

# Импорты для типов объектов
from .abstractions import (
    Effects, Behaviour, Constraints, ActionSpec,
    TransitionSpec, ConstructSpec, KindChain, InterruptionType,
    CallStackAction, ConditionValue, InterruptionMode, OriginType,
    RoleInListType, AppearanceType
)
from .cfg import Metadata, Node, Edge, CFG, NodeKind
from src.common_utils import SelfValidatedEnum


class EffectsExporter(ObjectExporter):
    """Экспортер для класса Effects."""
    
    def get_supported_types(self) -> List[Type]:
        return [Effects]
    
    def get_preferred_name(self, obj: Effects) -> str:
        # Генерируем имя на основе свойств
        parts = []
        if obj.interruption_stop:
            parts.append(f"stop_{obj.interruption_stop.value}")
        if obj.interruption_start:
            parts.append(f"start_{obj.interruption_start.value}")
        if obj.call_stack:
            parts.append(f"call_{obj.call_stack.value}")
        
        base_name = "_".join(parts) if parts else "empty_effect"
        return base_name
    
    def get_class_name(self, obj: Effects) -> str:
        return "Effect"
    
    def export_properties(self, obj: Effects) -> Dict[str, Any]:
        properties = {}
        if obj.interruption_stop:
            properties["interruption_stop"] = obj.interruption_stop
        if obj.interruption_start:
            properties["interruption_start"] = obj.interruption_start
        if obj.call_stack:
            properties["call_stack"] = obj.call_stack
        return properties
    
    def export_relationships(self, obj: Effects) -> Dict[str, List[Any]]:
        return {}


class BehaviourExporter(ObjectExporter):
    """Экспортер для класса Behaviour."""
    
    def get_supported_types(self) -> List[Type]:
        return [Behaviour]
    
    def get_preferred_name(self, obj: Behaviour) -> str:
        base_name = "behaviour"
        if obj.assumed_value is not None:
            base_name += f"_assumed_value_{obj.assumed_value}"

        if base_name == "behaviour":
            base_name = "empty_behaviour"
        return base_name
    
    def get_class_name(self, obj: Behaviour) -> str:
        return "Behaviour"
    
    def export_properties(self, obj: Behaviour) -> Dict[str, Any]:
        properties = {}
        if obj.assumed_value is not None:
            properties["assumed_value"] = obj.assumed_value
        return properties
    
    def export_relationships(self, obj: Behaviour) -> Dict[str, List[Any]]:
        return {}


class ConstraintsExporter(ObjectExporter):
    """Экспортер для класса Constraints."""
    
    def get_supported_types(self) -> List[Type]:
        return [Constraints]
    
    def get_preferred_name(self, obj: Constraints) -> str:
        parts = []
        if obj.condition_value is not None:
            parts.append(f"cond_{obj.condition_value.value}")
        if obj.interruption_mode:
            parts.append(f"mode_{obj.interruption_mode.value}")
        
        base_name = "_".join(parts) if parts else "empty_constraint"
        return base_name
    
    def get_class_name(self, obj: Constraints) -> str:
        return "Constraint"
    
    def export_properties(self, obj: Constraints) -> Dict[str, Any]:
        properties = {}
        if obj.condition_value is not None:
            properties["condition_value"] = obj.condition_value
        if obj.interruption_mode:
            properties["interruption_mode"] = obj.interruption_mode
        return properties
    
    def export_relationships(self, obj: Constraints) -> Dict[str, List[Any]]:
        return {}


class ActionSpecExporter(ObjectExporter):
    """Экспортер для класса ActionSpec."""
    
    def get_supported_types(self) -> List[Type]:
        return [ActionSpec]
    
    def get_preferred_name(self, obj: ActionSpec) -> str:
        base_name = f"action_{obj.name}"
        return base_name
    
    def get_class_name(self, obj: ActionSpec) -> str:
        return "ActionSpec"
    
    def export_properties(self, obj: ActionSpec) -> Dict[str, Any]:
        properties = {
            "role": obj.role,
            "kind": str(obj.kind)
        }
        if obj.generalization:
            properties["generalization"] = obj.generalization
        return properties
    
    def export_relationships(self, obj: ActionSpec) -> Dict[str, List[Any]]:
        relationships = {}
        
        # Экспортируем effects - возвращаем сами объекты
        if obj.effects:
            relationships["hasEffects"] = obj.effects
        
        # Экспортируем behaviour - возвращаем сам объект
        if obj.behaviour:
            relationships["hasBehaviour"] = [obj.behaviour]
        
        return relationships


class TransitionSpecExporter(ObjectExporter):
    """Экспортер для класса TransitionSpec."""
    
    def get_supported_types(self) -> List[Type]:
        return [TransitionSpec]
    
    def get_preferred_name(self, obj: TransitionSpec) -> str:
        base_name = f"transition_{obj.from_}_to_{obj.to}"
        return base_name
    
    def get_class_name(self, obj: TransitionSpec) -> str:
        return "TransitionSpec"
    
    def export_properties(self, obj: TransitionSpec) -> Dict[str, Any]:
        properties = {}
        if obj.from_:
            properties["from_"] = obj.from_
        if obj.to:
            properties["to"] = obj.to
        if obj.to_when_absent:
            if isinstance(obj.to_when_absent, list):
                properties["to_when_absent"] = obj.to_when_absent
            else:
                properties["to_when_absent"] = [obj.to_when_absent]
        return properties
    
    def export_relationships(self, obj: TransitionSpec) -> Dict[str, List[Any]]:
        relationships = {}
        
        # Экспортируем constraints - возвращаем сам объект
        if obj.constraints:
            relationships["hasConstraints"] = [obj.constraints]
        
        # Экспортируем effects - возвращаем сами объекты
        if obj.effects:
            relationships["hasEffects"] = obj.effects
        
        return relationships


class ConstructSpecExporter(ObjectExporter):
    """Экспортер для класса ConstructSpec."""
    
    def get_supported_types(self) -> List[Type]:
        return [ConstructSpec]
    
    def get_preferred_name(self, obj: ConstructSpec) -> str:
        base_name = f"construct_{obj.name}"
        return base_name
    
    def get_class_name(self, obj: ConstructSpec) -> str:
        return "ConstructSpec"
    
    def export_properties(self, obj: ConstructSpec) -> Dict[str, Any]:
        properties = {
            "name": obj.name,
            "kind": str(obj.kind)
        }
        if obj.ast_node:
            properties["ast_node"] = obj.ast_node
        return properties
    
    def export_relationships(self, obj: ConstructSpec) -> Dict[str, List[Any]]:
        relationships = {}
        
        # Экспортируем actions - возвращаем сами объекты
        if obj.actions:
            relationships["hasActions"] = obj.actions
        
        # Экспортируем transitions - возвращаем сами объекты
        if obj.transitions:
            relationships["hasTransitions"] = obj.transitions
        
        # Экспортируем effects - возвращаем сами объекты
        if obj.effects:
            relationships["hasEffects"] = obj.effects
        
        return relationships


class MetadataExporter(ObjectExporter):
    """Экспортер для класса Metadata."""
    
    def get_supported_types(self) -> List[Type]:
        return [Metadata]
    
    def get_preferred_name(self, obj: Metadata) -> str:
        parts = []
        if obj.abstract_action is not None:
            parts.append(f"a_{id(obj.abstract_action) % 1000_000}")
        if obj.abstract_transition is not None:
            parts.append(f"t_{id(obj.abstract_transition) % 1000_000}")
        if obj.wrapped_ast is not None:
            parts.append(f"w_{obj.wrapped_ast.ast_node['id']}")
        if obj.assumed_value is not None:
            parts.append(f"assumed_{obj.assumed_value}")
        if obj.primary is not None:
            parts.append(f"primary_{obj.primary}")
        if obj.call_count > 0:
            parts.append(f"calls_{obj.call_count}")
        if obj.has_corresponding_end is not None:
            parts.append(f"has_end_{obj.has_corresponding_end.id}")
        
        base_name = "_".join(parts) if parts else "empty_metadata"
        return base_name
    
    def get_class_name(self, obj: Metadata) -> str:
        return "Metadata"
    
    def export_properties(self, obj: Metadata) -> Dict[str, Any]:
        properties = {}
        if obj.assumed_value is not None:
            properties["assumed_value"] = obj.assumed_value
        if obj.assumed_value is not None:
            properties["assumed_value"] = obj.assumed_value
        if obj.primary is not None:
            properties["primary"] = obj.primary
        if obj.is_after_last is not None:
            properties["is_after_last"] = obj.is_after_last
        if obj.call_count > 0:
            properties["call_count"] = obj.call_count
        return properties
    
    def export_relationships(self, obj: Metadata) -> Dict[str, List[Any]]:
        relationships = {}
        
        # Экспортируем abstract_action - возвращаем сам объект
        if obj.abstract_action:
            relationships["hasAbstractAction"] = [obj.abstract_action]
        
        # Экспортируем abstract_transition - возвращаем сам объект
        if obj.abstract_transition:
            relationships["hasAbstractTransition"] = [obj.abstract_transition]
        
        # Экспортируем has_corresponding_end - возвращаем сам объект
        if obj.has_corresponding_end:
            relationships["hasCorrespondingEnd"] = [obj.has_corresponding_end]
        
        return relationships


class NodeExporter(ObjectExporter):
    """Экспортер для класса Node."""
    
    def get_supported_types(self) -> List[Type]:
        return [Node]
    
    def get_preferred_name(self, obj: Node) -> str:
        # Используем существующий id как базу для имени
        base_name = obj.id
        return base_name
    
    def get_class_name(self, obj: Node) -> str:
        return "Node"
    
    def export_properties(self, obj: Node) -> Dict[str, Any]:
        properties = {
            "id": obj.id,
            "role": obj.role,
            "kind": obj.kind
        }
        return properties
    
    def export_relationships(self, obj: Node) -> Dict[str, List[Any]]:
        relationships = {}
        
        # Экспортируем metadata - возвращаем сам объект
        if obj.metadata:
            relationships["hasMetadata"] = [obj.metadata]
        
        # Экспортируем effects - возвращаем сами объекты
        if obj.effects:
            relationships["hasEffects"] = obj.effects
        
        return relationships


class EdgeExporter(ObjectExporter):
    """Экспортер для класса Edge."""
    
    def get_supported_types(self) -> List[Type]:
        return [Edge]
    
    def get_preferred_name(self, obj: Edge) -> str:
        # Используем существующий id как базу для имени
        base_name = obj.id
        return base_name
    
    def get_class_name(self, obj: Edge) -> str:
        return "Edge"
    
    def export_properties(self, obj: Edge) -> Dict[str, Any]:
        properties = {
            "id": obj.id,
            "src": obj.src,
            "dst": obj.dst
        }
        return properties
    
    def export_relationships(self, obj: Edge) -> Dict[str, List[Any]]:
        relationships = {}
        
        # Экспортируем metadata - возвращаем сам объект
        if obj.metadata:
            relationships["hasMetadata"] = [obj.metadata]
        
        # Экспортируем constraints - возвращаем сам объект
        if obj.constraints:
            relationships["hasConstraints"] = [obj.constraints]
        
        # Экспортируем effects - возвращаем сами объекты
        if obj.effects:
            relationships["hasEffects"] = obj.effects
        
        return relationships


class CFGExporter(ObjectExporter):
    """Экспортер для класса CFG."""
    
    def get_supported_types(self) -> List[Type]:
        return [CFG]
    
    def get_preferred_name(self, obj: CFG) -> str:
        # Используем существующий id как базу для имени
        base_name = obj.id
        return base_name
    
    def get_class_name(self, obj: CFG) -> str:
        return "CFG"
    
    def export_properties(self, obj: CFG) -> Dict[str, Any]:
        properties = {
            "id": obj.id,
            "name": obj.name
        }
        return properties
    
    def export_relationships(self, obj: CFG) -> Dict[str, List[Any]]:
        relationships = {}
        
        # Экспортируем nodes - возвращаем сами объекты
        if obj.nodes:
            relationships["hasNodes"] = list(obj.nodes.values())
        
        # Экспортируем edges - возвращаем сами объекты
        if obj.edges:
            relationships["hasEdges"] = obj.edges
        
        # Экспортируем begin и end nodes - возвращаем сами объекты
        if obj.begin_node:
            relationships["hasBegin"] = [obj.begin_node]
        
        if obj.end_node:
            relationships["hasEnd"] = [obj.end_node]
        
        return relationships
