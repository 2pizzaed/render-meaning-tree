"""
Конкретные экспортеры для каждого типа объектов из abstractions.py и cfg.py.
"""

from typing import Any

from src.cfg.abstractions import InterruptionType, OptionalBoolValue
from src.locale_utils import Locales

from ..ast_analyzer import ASTNodeAnalyzer
from . import ASTNodeWrapper

# Импорты для типов объектов
from .abstractions import (
    ActionSpec,
    Behaviour,
    Constraints,
    ConstructSpec,
    Effects,
    SituationState,
    TransitionSpec,
)
from .cfg import CFG, Edge, Metadata, Node, TraceAct
from .loqi_exporter import NameRegistry, ObjectExporter
from .reachability import PathInfo

# use classmethod as decorator
registered = ObjectExporter.register_class
loc = Locales("definitions")

# Кэш для конструктов (ленивая загрузка)
_constructs_cache: dict[str, ConstructSpec] | None = None

def _find_construct_for_ast_node(wrapped_ast: ASTNodeWrapper | None) -> ConstructSpec | None:
    """Находит конструкт, соответствующий AST-узлу.
    
    Для действий с kind: auto нужно использовать конструкт, соответствующий
    самому AST-узлу, а не родительский конструкт действия.
    
    Args:
        wrapped_ast: Обёртка AST-узла
        
    Returns:
        ConstructSpec, соответствующий AST-узлу, или None если не найден
    """
    if not wrapped_ast:
        return None
    
    global _constructs_cache
    if _constructs_cache is None:
        from src.cfg.abstractions import load_constructs
        _constructs_cache = load_constructs("constructs.yml", debug=False)
    
    ast_node = wrapped_ast.ast_node
    if not isinstance(ast_node, dict):
        return None
    
    node_type = ast_node.get("type")
    if not node_type:
        return None
    
    for construct in _constructs_cache.values():
        if node_type in construct.supported_ast_nodes():
            return construct
    
    return None

@registered
class EffectsExporter(ObjectExporter):
    """Экспортер для класса Effects."""

    def get_supported_types(self) -> list[type]:
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

    def export_properties(self, obj: Effects) -> dict[str, Any]:
        properties = {}
        if obj.interruption_stop:
            properties["interruption_stop"] = obj.interruption_stop
        if obj.interruption_start:
            properties["interruption_start"] = obj.interruption_start
        if obj.call_stack:
            properties["call_stack"] = obj.call_stack
        return properties

    def export_relationships(self, obj: Effects) -> dict[str, list[Any]]:
        return {}


@registered
class BehaviourExporter(ObjectExporter):
    """Экспортер для класса Behaviour."""

    def get_supported_types(self) -> list[type]:
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

    def export_properties(self, obj: Behaviour) -> dict[str, Any]:
        properties = {}
        if obj.assumed_value is not None:
            properties["assumed_value"] = obj.assumed_value
        return properties

    def export_relationships(self, obj: Behaviour) -> dict[str, list[Any]]:
        return {}


@registered
class ConstraintsExporter(ObjectExporter):
    """Экспортер для класса Constraints."""

    def get_supported_types(self) -> list[type]:
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

    def export_properties(self, obj: Constraints) -> dict[str, Any]:
        properties = {}
        if obj.condition_value is not None:
            properties["condition_value"] = obj.condition_value
        if obj.interruption_mode:
            properties["interruption_mode"] = obj.interruption_mode
        return properties

    def export_relationships(self, obj: Constraints) -> dict[str, list[Any]]:
        return {}


@registered
class ActionSpecExporter(ObjectExporter):
    """Экспортер для класса ActionSpec."""

    def get_supported_types(self) -> list[type]:
        return [ActionSpec]

    def get_preferred_name(self, obj: ActionSpec) -> str:
        base_name = f"action_{obj.name}"
        return base_name

    def get_class_name(self, obj: ActionSpec) -> str:
        return "ActionSpec"

    def export_properties(self, obj: ActionSpec) -> dict[str, Any]:
        properties = {
            "role": obj.role,
        }
        if obj.kind:
            kinds = obj.kind.to_enums()
            if kinds:
                # взять первый, самый "смысловой" тип (раз все перечислить нельзя)
                properties["kind"] = kinds[0].value
        if obj.generalization:
            properties["generalization"] = obj.generalization
        properties["_locale_trace_name"] = obj._locale_trace_name
        properties["_locale_pronoun"] = obj._locale_pronoun
        return properties

    def export_relationships(self, obj: ActionSpec) -> dict[str, list[Any]]:
        relationships = {}

        # ConstructSpec
        if obj.construct:
            relationships["hasConstruct"] = [obj.construct]

        # Экспортируем effects - возвращаем сами объекты
        if obj.effects:
            relationships["hasEffects"] = obj.effects

        # Экспортируем behaviour
        if obj.behaviour:
            relationships["hasBehaviour"] = [obj.behaviour]

        return relationships


@registered
class TransitionSpecExporter(ObjectExporter):
    """Экспортер для класса TransitionSpec."""

    def get_supported_types(self) -> list[type]:
        return [TransitionSpec]

    def get_preferred_name(self, obj: TransitionSpec) -> str:
        base_name = f"transition_{obj.from_}_to_{obj.to}"
        return base_name

    def get_class_name(self, obj: TransitionSpec) -> str:
        return "TransitionSpec"

    @classmethod
    def _get_action(cls, obj: TransitionSpec, action_name: str) -> ActionSpec:
        action_obj = obj.construct.find_action_by_role(action_name)
        return action_obj

    def export_properties(self, obj: TransitionSpec) -> dict[str, Any]:
        properties = {}
        return properties

    def export_relationships(self, obj: TransitionSpec) -> dict[str, list[Any]]:
        relationships = {}

        if obj.from_:
            relationships["from_"] = [self._get_action(obj, obj.from_)]
        if obj.to:
            relationships["to_"] = [self._get_action(obj, obj.to)]
        if obj.to_when_absent:
            if isinstance(obj.to_when_absent, list):
                to_when_absent_list = obj.to_when_absent
            else:
                to_when_absent_list = [obj.to_when_absent]

            relationships["to_when_absent"] = [
                self._get_action(obj, action_name)
                for action_name in to_when_absent_list
            ]

        # ConstructSpec
        if obj.construct:
            relationships["hasConstruct"] = [obj.construct]

        # Экспортируем constraints
        if obj.constraints:
            relationships["hasConstraints"] = [obj.constraints]

        # Экспортируем effects - возвращаем сами объекты
        if obj.effects:
            relationships["hasEffects"] = obj.effects

        return relationships


@registered
class ConstructSpecExporter(ObjectExporter):
    """Экспортер для класса ConstructSpec."""

    def get_supported_types(self) -> list[type]:
        return [ConstructSpec]

    def get_preferred_name(self, obj: ConstructSpec) -> str:
        base_name = f"construct_{obj.name}"
        return base_name

    def get_class_name(self, obj: ConstructSpec) -> str:
        return "ConstructSpec"

    def export_properties(self, obj: ConstructSpec) -> dict[str, Any]:
        properties = {
            "name": obj.name,
        }
        if obj.kind:
            kinds = obj.kind.to_enums()
            if kinds:
                # взять первый, самый "смысловой" тип (раз все перечислить нельзя)
                properties["kind"] = kinds[0].value
        # if obj.ast_node:   #internal.
        #     properties["ast_node"] = obj.ast_node
        properties["_locale_trace_name"] = obj._locale_trace_name
        properties["_locale_pronoun"] = obj._locale_pronoun
        return properties

    def export_relationships(self, obj: ConstructSpec) -> dict[str, list[Any]]:
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


@registered
class MetadataExporter(ObjectExporter):
    """Экспортер для класса Metadata."""

    def get_supported_types(self) -> list[type]:
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

    def export_properties(self, obj: Metadata) -> dict[str, Any]:
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

    def export_relationships(self, obj: Metadata) -> dict[str, list[Any]]:
        relationships = {}

        # Экспортируем abstract_action
        if obj.abstract_action:
            relationships["hasAbstractAction"] = [obj.abstract_action]

        if obj.wrapped_ast:
            relationships["belongsToASTNode"] = [obj.wrapped_ast]

        # Экспортируем abstract_transition
        if obj.abstract_transition:
            relationships["hasAbstractTransition"] = [obj.abstract_transition]

        # Экспортируем has_corresponding_end
        if obj.has_corresponding_end:
            relationships["hasCorrespondingEnd"] = [obj.has_corresponding_end]

        return relationships


@registered
class NodeExporter(ObjectExporter):
    """Экспортер для класса Node."""

    def get_supported_types(self) -> list[type]:
        return [Node]

    def get_preferred_name(self, obj: Node) -> str:
        # Используем существующий id как базу для имени
        base_name = obj.id
        return base_name

    def get_class_name(self, obj: Node) -> str:
        return "Node"

    def export_metadata(self, obj: Node) -> dict[str, Any]:
        loc_key = None
        if action := obj.metadata.abstract_action:
            # Для действий с kind: auto используем конструкт, соответствующий AST-узлу,
            # а не родительский конструкт действия
            if action._locale_trace_name:
                loc_key = action._locale_trace_name
            else:
                # Ищем конструкт для AST-узла
                ast_construct = _find_construct_for_ast_node(obj.metadata.wrapped_ast)
                if ast_construct and ast_construct._locale_trace_name:
                    loc_key = ast_construct._locale_trace_name

        if loc_key:
            localized = loc.get(loc_key, "ru") or ""
        else:
            localized = ""

        ast: ASTNodeWrapperExporter = self.get_exporter_for(obj.metadata.wrapped_ast)
        code_info = ast.get_code_piece_ext(obj.metadata.wrapped_ast)
        if code_info:
            localized += (" " if localized else '') + code_info
        entries = {
            "RU.localizedName": localized,
        }
        return entries

    def export_properties(self, obj: Node) -> dict[str, Any]:
        properties = {
            "id": obj.id,
            # "role": obj.role_in_construct,
            "kind": obj.kind
        }
        return properties

    def export_relationships(self, obj: Node) -> dict[str, list[Any]]:
        relationships = {}

        # hasEdges TODO

        # Экспортируем metadata
        if obj.metadata:
            relationships["hasMetadata"] = [obj.metadata]

        # Экспортируем effects - возвращаем сами объекты
        if obj.effects:
            relationships["hasEffects"] = obj.effects

        return relationships


@registered
class EdgeExporter(ObjectExporter):
    """Экспортер для класса Edge."""

    def get_supported_types(self) -> list[type]:
        return [Edge]

    def get_preferred_name(self, obj: Edge) -> str:
        # Используем существующий id как базу для имени
        base_name = obj.id
        return base_name

    def get_class_name(self, obj: Edge) -> str:
        return "Edge"

    def export_properties(self, obj: Edge) -> dict[str, Any]:
        properties = {
            "id": obj.id,
        }
        return properties

    def export_relationships(self, obj: Edge) -> dict[str, list[Any]]:
        relationships: dict[str, list[Any]] = {
            "hasSource": [obj.cfg.nodes[obj.src]],
            "hasDestination": [obj.cfg.nodes[obj.dst]],
        }

        # Экспортируем metadata
        if obj.metadata:
            relationships["hasMetadata"] = [obj.metadata]

        # Экспортируем constraints
        if obj.constraints:
            relationships["hasConstraints"] = [obj.constraints]

        # Экспортируем effects - возвращаем сами объекты
        if obj.effects:
            relationships["hasEffects"] = obj.effects

        return relationships


@registered
class PathInfoExporter(ObjectExporter):
    """Экспортер для класса PathInfo."""
    def get_supported_types(self) -> list[type]:
        return [PathInfo]

    def get_class_name(self, obj: PathInfo) -> str:
        return "PathInfo"

    def add_all_paths(self, paths: list[PathInfo]) -> None:
        self._paths = paths

    def get_preferred_name(self, obj: PathInfo) -> str:
        if hasattr(self, "_paths") and obj in self._paths:
            index = self._paths.index(obj)
            return f"path_info_{index}"
        path_id = getattr(obj, "id", None)
        if path_id:
            return f"path_info_{path_id}"
        return f"path_info_{id(obj) % 100_000}"

    def export_properties(self, obj: PathInfo) -> dict[str, Any]:
        properties: dict[str, Any] = {}

        path_id = getattr(obj, "id", None)
        if path_id is not None:
            properties["id"] = path_id

        if obj.is_direct is not None:
            properties["is_direct"] = obj.is_direct
        else:
            raise ValueError("PathInfo is incomplete")

        # ways_count = getattr(obj, "ways_count", None)
        # if ways_count is not None:
        #     properties["ways_count"] = ways_count

        numeric_metrics = {
            "ast_actions": obj.ast_actions,
            "transparent_actions": obj.transparent_actions,
            "opaque_actions": obj.opaque_actions,
            "conditions": obj.conditions,
            "frame_changes": obj.frame_changes,
            "frames_added": obj.frames_added,
            "frames_dropped": obj.frames_dropped,
        }

        for key, value in numeric_metrics.items():
            if value is not None:
                properties[key] = value

        return properties

    def export_relationships(self, obj: PathInfo) -> dict[str, list[Any]]:
        relationships: dict[str, list[Any]] = {}

        source_node = getattr(obj, "from_", None)
        if source_node:
            relationships["from_"] = [source_node]
        elif obj.cfg:
            src_id = getattr(obj, "src", None)
            if src_id:
                relationships["from_"] = [obj.cfg.nodes[src_id]]

        destination_node = getattr(obj, "to_", None)
        if destination_node:
            relationships["to_"] = [destination_node]
        elif obj.cfg:
            dst_id = getattr(obj, "dst", None)
            if dst_id:
                relationships["to_"] = [obj.cfg.nodes[dst_id]]

        # if obj.metadata:
        #     relationships["hasMetadata"] = [obj.metadata]

        if obj.constraints:
            relationships["hasConstraints"] = [obj.constraints]

        if obj.effects:
            relationships["hasEffects"] = obj.effects

        if obj.firstMiddleAction:
            relationships["hasFirstMiddleAction"] = [obj.firstMiddleAction]

        if obj.firstMiddleCondition:
            relationships["hasFirstMiddleCondition"] = [obj.firstMiddleCondition]

        if obj.firstMiddleFrameChange:
            relationships["hasFirstMiddleFrameChange"] = [obj.firstMiddleFrameChange]

        return relationships


@registered
class CFGExporter(ObjectExporter):
    """Экспортер для класса CFG."""

    def get_supported_types(self) -> list[type]:
        return [CFG]

    def get_preferred_name(self, obj: CFG) -> str:
        # Используем существующий id как базу для имени
        base_name = obj.id
        return base_name

    def get_class_name(self, obj: CFG) -> str:
        return "CFG"

    def export_properties(self, obj: CFG) -> dict[str, Any]:
        properties = {
            "id": obj.id,
            "name": obj.name
        }
        return properties

    def export_relationships(self, obj: CFG) -> dict[str, list[Any]]:
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


@registered
class ASTNodeWrapperExporter(ObjectExporter):
    """Экспортер для класса ASTNodeWrapper."""

    def get_supported_types(self) -> list[type]:
        return [ASTNodeWrapper]

    def get_preferred_name(self, obj: ASTNodeWrapper) -> str:
        info = obj.describe()
        if not info['ast_id']:
            info['ast_id'] = id(obj) % 100_000
        info['ast_id'] = str(info['ast_id'])
        return 'ast_' + ('_'.join(info.values()))

    def get_class_name(self, obj: ASTNodeWrapper) -> str:
        return "ASTNodeWrapper"

    def get_ast_node_analyzer(self, obj: ASTNodeWrapper) -> ASTNodeAnalyzer | None:
        root_node = obj.get_root()
        if root_node:
            analyzer = root_node._astnodeanalyzer
            if analyzer:
                return analyzer
        return None

    def get_code_piece_ext(self, obj: ASTNodeWrapper) -> str | None:
        ast_node = obj.ast_node
        if not isinstance(ast_node, dict):
            # # try to go up ...?
            # obj = obj.parent.parent if obj.parent else obj
            # if not isinstance(ast_node, dict):
            #     # return 'None: not a dict!!!'
            #     return None
            # return 'None: not a dict!!!'
            return None
        ast_id = ast_node['id']
        analyzer = self.get_ast_node_analyzer(obj)
        if analyzer:
            code_piece = analyzer.get_code_piece_by_id(ast_id) or ''
            code_piece = code_piece.strip()

            if '\n' in code_piece or analyzer.is_compound_statement(ast_id):
                # Составное действие.
                line = analyzer.get_code_line_number_by_id(ast_id)
                s = f'на строке {line}' if line else ''
                return s
            else:
                # Простые действия и выражения: берем целиком.
                return f"<code>{code_piece}</code>"
        # return 'None: no analyzer!!!'
        return None

    def export_properties(self, obj: ASTNodeWrapper) -> dict[str, Any]:
        # import json
        properties = obj.describe()
        # properties["ast_node"] = json.dumps(obj.ast_node)
        # properties["current_condition_value"] = ???
        if properties["ast_id"]:
            properties["_code_piece"] = self.get_code_piece_ext(obj) or ''
        return properties

    def export_relationships(self, obj: ASTNodeWrapper) -> dict[str, list[Any]]:
        relationships = {}

        # Экспортируем parent
        if obj.parent:
            relationships["hasParent"] = [obj.parent]

        return relationships


@registered
class TraceActExporter(ObjectExporter):
    """Экспортер для класса TraceAct.
    
    Обеспечивает экспорт актов трассы в LOQI-формат, включая:
    - Свойства акта (condition_value, is_known_correct, active)
    - Связи с AST-узлами, CFG-узлами, спецификациями действий
    - Связь directlyBeforeOf для формирования цепочки выполнения
    - Связь hasActAsCorrespondingEnd для BEGIN/END пар
    
    Метод add_full_trace позволяет установить полную трассу для корректного
    именования актов и установки связей directlyBeforeOf.
    """

    def __init__(
        self,
        name_registry: NameRegistry | None = None,
        exporters: dict[type, "ObjectExporter"] | None = None,
    ):
        super().__init__(name_registry, exporters)
        self._trace: list[TraceAct] = []

    def get_supported_types(self) -> list[type]:
        return [TraceAct]

    def get_class_name(self, obj: TraceAct) -> str:
        return "TraceAct"

    def add_full_trace(self, trace: list[TraceAct]) -> None:
        """Устанавливает полную трассу для корректного экспорта связей.
        
        Этот метод должен быть вызван перед экспортом актов трассы, чтобы
        экспортер мог правильно установить связи directlyBeforeOf и корректно
        именовать акты по их индексу в трассе.
        
        Args:
            trace: Полный список актов трассы в порядке выполнения
        """
        self._trace = trace

    def export_properties(self, obj: TraceAct) -> dict[str, Any]:
        condition_value = obj.condition_value
        if condition_value is None:
            condition_value = OptionalBoolValue.NO_VALUE

        properties = {
            "condition_value": condition_value,
            "is_known_correct": obj.is_known_correct,
        }
        return properties

    def export_metadata(self, obj: TraceAct) -> dict[str, Any]:
        node_exporter: NodeExporter = self.get_exporter_for(obj.cfg_node)
        if node_exporter:
            localized = node_exporter.export_metadata(obj.cfg_node)["RU.localizedName"] or ""
        else:
            localized = ''
        entries = {
            "RU.localizedName": localized,
        }
        return entries

    def get_preferred_name(self, obj: TraceAct) -> str:
        if self._trace:
            index = self._trace.index(obj)
        else:
            index: str | int = obj.wrapped_ast.ast_node.get(
                "id", f"unknown_{id(obj) % 100_000}")
        return f"trace_act_{index}_{obj.cfg_node.kind.value.lower()}"

    def export_relationships(self, obj: TraceAct) -> dict[str, list[Any]]:
        """Экспортирует связи TraceAct с другими объектами.
        
        Экспортирует следующие связи:
        - hasASTNode: связь с AST-узлом
        - hasCFGNode: связь с CFG-узлом
        - hasActionSpec: связь со спецификацией действия (если есть)
        - hasActAsCorrespondingEnd: связь с соответствующим актом конца блока
                                   (для BEGIN/END пар)
        - directlyBeforeOf: связь со следующим актом в трассе, формирующая цепочку
                          последовательности выполнения программы
        
        Args:
            obj: Акты трассы для экспорта связей
        
        Returns:
            Словарь с именами связей и списками связанных объектов
        """
        relationships = {
            "hasASTNode": [obj.wrapped_ast],
            "hasCFGNode": [obj.cfg_node],
            "hasActionSpec": [obj.action_spec],
            "hasActAsCorrespondingEnd": [obj.corresponding_end] if obj.corresponding_end else [],
            "directlyBeforeOf": [obj.directly_before_of] if obj.directly_before_of else [],
        }
        return relationships


@registered
class SituationStateExporter(ObjectExporter):
    """Экспортер для класса TraceAct."""

    def export_relationships(self, obj: Any) -> dict[str, list[Any]]:
        return {}

    def get_supported_types(self) -> list[type]:
        return [SituationState]

    def get_class_name(self, obj: SituationState) -> str:
        return "State"

    def export_properties(self, obj: SituationState) -> dict[str, Any]:
        properties: dict[str, InterruptionType] = {
            "interruption_state": obj.interruption_state,
        }
        return properties

    def get_preferred_name(self, obj: SituationState) -> str:
        return f"main_state_{id(obj) % 100_000}"
