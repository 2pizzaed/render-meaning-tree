"""
Конкретные экспортеры для каждого типа объектов из abstractions.py и cfg.py.
"""

from typing import Any, Dict, List, Type
from .loqi_exporter import ObjectExporter

# Импорты для типов объектов
from .abstractions import (
    Effects, Identification, Behaviour, Constraints, ActionSpec,
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
        
        base_name = "_".join(parts) if parts else "effect"
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
    
    def export_relationships(self, obj: Effects) -> Dict[str, List[str]]:
        return {}


class IdentificationExporter(ObjectExporter):
    """Экспортер для класса Identification."""
    
    def get_supported_types(self) -> List[Type]:
        return [Identification]
    
    def get_preferred_name(self, obj: Identification) -> str:
        parts = []
        if obj.origin:
            parts.append(obj.origin.value)
        if obj.property:
            parts.append(obj.property)
        if obj.role_in_list:
            parts.append(obj.role_in_list.value)
        
        base_name = "_".join(parts) if parts else "identification"
        return base_name
    
    def get_class_name(self, obj: Identification) -> str:
        return "Identification"
    
    def export_properties(self, obj: Identification) -> Dict[str, Any]:
        properties = {}
        if obj.origin:
            properties["origin"] = obj.origin
        if obj.property:
            properties["property"] = obj.property
        if obj.property_path:
            properties["property_path"] = obj.property_path
        if obj.role_in_list:
            properties["role_in_list"] = obj.role_in_list
        return properties
    
    def export_relationships(self, obj: Identification) -> Dict[str, List[str]]:
        return {}


class BehaviourExporter(ObjectExporter):
    """Экспортер для класса Behaviour."""
    
    def get_supported_types(self) -> List[Type]:
        return [Behaviour]
    
    def get_preferred_name(self, obj: Behaviour) -> str:
        base_name = "behaviour"
        if obj.assumed_value is not None:
            base_name += f"_{obj.assumed_value}"
        return base_name
    
    def get_class_name(self, obj: Behaviour) -> str:
        return "Behaviour"
    
    def export_properties(self, obj: Behaviour) -> Dict[str, Any]:
        properties = {}
        if obj.assumed_value is not None:
            properties["assumed_value"] = obj.assumed_value
        return properties
    
    def export_relationships(self, obj: Behaviour) -> Dict[str, List[str]]:
        return {}


class ConstraintsExporter(ObjectExporter):
    """Экспортер для класса Constraints."""
    
    def get_supported_types(self) -> List[Type]:
        return [Constraints]
    
    def get_preferred_name(self, obj: Constraints) -> str:
        parts = []
        if obj.condition_value is not None:
            parts.append(f"cond_{obj.condition_value}")
        if obj.interruption_mode:
            parts.append(f"mode_{obj.interruption_mode.value}")
        
        base_name = "_".join(parts) if parts else "constraint"
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
    
    def export_relationships(self, obj: Constraints) -> Dict[str, List[str]]:
        return {}


class ActionSpecExporter(ObjectExporter):
    """Экспортер для класса ActionSpec."""
    
    def get_supported_types(self) -> List[Type]:
        return [ActionSpec]
    
    def get_preferred_name(self, obj: ActionSpec) -> str:
        base_name = f"action_{obj.role}"
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
    
    def export_relationships(self, obj: ActionSpec) -> Dict[str, List[str]]:
        relationships = {}
        
        # Экспортируем effects как отдельные объекты
        effect_names = []
        for effect in obj.effects:
            effect_name = self.get_registered_name_for_object(effect)
            if effect_name:
                effect_names.append(effect_name)
        if effect_names:
            relationships["hasEffects"] = effect_names
        
        # Экспортируем behaviour
        if obj.behaviour:
            behaviour_name = self.get_registered_name_for_object(obj.behaviour)
            if behaviour_name:
                relationships["hasBehaviour"] = [behaviour_name]
        
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
    
    def export_relationships(self, obj: TransitionSpec) -> Dict[str, List[str]]:
        relationships = {}
        
        # Экспортируем constraints
        if obj.constraints:
            constraint_name = self.get_registered_name_for_object(obj.constraints)
            if constraint_name:
                relationships["hasConstraints"] = [constraint_name]
        
        # Экспортируем effects
        effect_names = []
        for effect in obj.effects:
            effect_name = self.get_registered_name_for_object(effect)
            if effect_name:
                effect_names.append(effect_name)
        if effect_names:
            relationships["hasEffects"] = effect_names
        
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
    
    def export_relationships(self, obj: ConstructSpec) -> Dict[str, List[str]]:
        relationships = {}
        
        # Экспортируем actions
        action_names = []
        for action in obj.actions:
            action_name = self.get_registered_name_for_object(action)
            if action_name:
                action_names.append(action_name)
        if action_names:
            relationships["hasActions"] = action_names
        
        # Экспортируем transitions
        transition_names = []
        for transition in obj.transitions:
            transition_name = self.get_registered_name_for_object(transition)
            if transition_name:
                transition_names.append(transition_name)
        if transition_names:
            relationships["hasTransitions"] = transition_names
        
        # Экспортируем effects
        effect_names = []
        for effect in obj.effects:
            effect_name = self.get_registered_name_for_object(effect)
            if effect_name:
                effect_names.append(effect_name)
        if effect_names:
            relationships["hasEffects"] = effect_names
        
        return relationships


class MetadataExporter(ObjectExporter):
    """Экспортер для класса Metadata."""
    
    def get_supported_types(self) -> List[Type]:
        return [Metadata]
    
    def get_preferred_name(self, obj: Metadata) -> str:
        parts = []
        if obj.assumed_value is not None:
            parts.append(f"assumed_{obj.assumed_value}")
        if obj.primary is not None:
            parts.append(f"primary_{obj.primary}")
        if obj.call_count > 0:
            parts.append(f"calls_{obj.call_count}")
        if obj.has_corresponding_end is not None:
            parts.append(f"has_end_{obj.has_corresponding_end.id}")
        
        base_name = "_".join(parts) if parts else "metadata"
        return base_name
    
    def get_class_name(self, obj: Metadata) -> str:
        return "Metadata"
    
    def export_properties(self, obj: Metadata) -> Dict[str, Any]:
        properties = {}
        if obj.assumed_value is not None:
            properties["assumed_value"] = obj.assumed_value
        if obj.primary is not None:
            properties["primary"] = obj.primary
        if obj.is_after_last is not None:
            properties["is_after_last"] = obj.is_after_last
        if obj.call_count > 0:
            properties["call_count"] = obj.call_count
        return properties
    
    def export_relationships(self, obj: Metadata) -> Dict[str, List[str]]:
        relationships = {}
        
        # Экспортируем abstract_action
        if obj.abstract_action:
            action_name = self.get_registered_name_for_object(obj.abstract_action)
            if action_name:
                relationships["hasAbstractAction"] = [action_name]
        
        # Экспортируем abstract_transition
        if obj.abstract_transition:
            transition_name = self.get_registered_name_for_object(obj.abstract_transition)
            if transition_name:
                relationships["hasAbstractTransition"] = [transition_name]
        
        # Экспортируем has_corresponding_end
        if obj.has_corresponding_end:
            end_name = self.get_registered_name_for_object(obj.has_corresponding_end)
            if end_name:
                relationships["hasCorrespondingEnd"] = [end_name]
        
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
    
    def export_relationships(self, obj: Node) -> Dict[str, List[str]]:
        relationships = {}
        
        # Экспортируем metadata
        if obj.metadata:
            metadata_name = self.get_registered_name_for_object(obj.metadata)
            if metadata_name:
                relationships["hasMetadata"] = [metadata_name]
        
        # Экспортируем effects
        effect_names = []
        for effect in obj.effects:
            effect_name = self.get_registered_name_for_object(effect)
            if effect_name:
                effect_names.append(effect_name)
        if effect_names:
            relationships["hasEffects"] = effect_names
        
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
    
    def export_relationships(self, obj: Edge) -> Dict[str, List[str]]:
        relationships = {}
        
        # Экспортируем metadata
        if obj.metadata:
            metadata_name = self.get_registered_name_for_object(obj.metadata)
            if metadata_name:
                relationships["hasMetadata"] = [metadata_name]
        
        # Экспортируем constraints
        if obj.constraints:
            constraint_name = self.get_registered_name_for_object(obj.constraints)
            if constraint_name:
                relationships["hasConstraints"] = [constraint_name]
        
        # Экспортируем effects
        effect_names = []
        for effect in obj.effects:
            effect_name = self.get_registered_name_for_object(effect)
            if effect_name:
                effect_names.append(effect_name)
        if effect_names:
            relationships["hasEffects"] = effect_names
        
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
    
    def export_relationships(self, obj: CFG) -> Dict[str, List[str]]:
        relationships = {}
        
        # Экспортируем nodes
        node_names = []
        for node in obj.nodes.values():
            node_name = self.get_registered_name_for_object(node)
            if node_name:
                node_names.append(node_name)
        if node_names:
            relationships["hasNodes"] = node_names
        
        # Экспортируем edges
        edge_names = []
        for edge in obj.edges:
            edge_name = self.get_registered_name_for_object(edge)
            if edge_name:
                edge_names.append(edge_name)
        if edge_names:
            relationships["hasEdges"] = edge_names
        
        # Экспортируем begin и end nodes
        if obj.begin_node:
            begin_name = self.get_registered_name_for_object(obj.begin_node)
            if begin_name:
                relationships["hasBegin"] = [begin_name]
        
        if obj.end_node:
            end_name = self.get_registered_name_for_object(obj.end_node)
            if end_name:
                relationships["hasEnd"] = [end_name]
        
        return relationships
