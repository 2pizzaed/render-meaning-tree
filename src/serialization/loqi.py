from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, TypeVar

from src.locale_utils import Locales


class LoqiSerializationError(RuntimeError):
    pass


class LoqiAdapterNotFoundError(LoqiSerializationError):
    pass


class LoqiDomainMismatchError(LoqiSerializationError):
    pass


@dataclass(frozen=True, slots=True)
class LoqiMetadataEntry:
    name: str
    value: LoqiScalar


@dataclass(frozen=True, slots=True)
class LoqiEnumLiteral:
    enum_name: str
    literal: str


@dataclass(frozen=True, slots=True)
class LoqiObjectRef:
    object_id: str


LoqiScalar = str | int | bool | LoqiEnumLiteral


@dataclass(frozen=True, slots=True)
class LoqiProperty:
    name: str
    value: LoqiScalar | None
    metadata: tuple[LoqiMetadataEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationshipLink:
    name: str
    targets: tuple[LoqiObjectRef, ...]
    metadata: tuple[LoqiMetadataEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class LoqiObjectSpec:
    properties: tuple[LoqiProperty, ...] = ()
    relationship_links: tuple[RelationshipLink, ...] = ()
    metadata: tuple[LoqiMetadataEntry, ...] = ()


@dataclass(slots=True)
class LoqiObject:
    object_id: str
    type_name: str
    properties: list[LoqiProperty] = field(default_factory=list)
    relationship_links: list[RelationshipLink] = field(default_factory=list)
    metadata: list[LoqiMetadataEntry] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LoqiVariableAssignment:
    variable_name: str
    object_id: str


@dataclass(frozen=True, slots=True)
class LoqiRenderResult:
    roots: tuple[LoqiObjectRef, ...]
    objects: tuple[LoqiObject, ...]
    variables: tuple[LoqiVariableAssignment, ...] = ()


T = TypeVar("T")


class LoqiAdapter[T](Protocol):
    def type_name(self, obj: T) -> str: ...

    def describe(self, obj: T, ctx: LoqiAdapterContext) -> LoqiObjectSpec: ...


@dataclass(frozen=True, slots=True)
class LoqiAdapterContext:
    serializer: LoqiSerializer
    current_object: LoqiObject | None = None
    state: dict[str, Any] = field(default_factory=dict)

    def with_state(self, **state_updates: Any) -> LoqiAdapterContext:
        next_state = dict(self.state)
        next_state.update(state_updates)
        return LoqiAdapterContext(
            serializer=self.serializer,
            current_object=self.current_object,
            state=next_state,
        )

    def require_state(self, key: str) -> Any:
        if key not in self.state:
            raise LoqiSerializationError(f"Required serializer state {key!r} is missing")
        return self.state[key]

    def require_current_object(self) -> LoqiObject:
        if self.current_object is None:
            raise LoqiSerializationError("Current Loqi object is not available in this adapter context")
        return self.current_object

    def enum(self, enum_name: str, literal: str) -> LoqiEnumLiteral:
        return LoqiEnumLiteral(enum_name=enum_name, literal=literal)

    def metadata_entry(
        self,
        name: str,
        value: Any,
        *,
        enum_name: str | None = None,
        value_map: dict[Any, str] | None = None,
    ) -> LoqiMetadataEntry:
        scalar = self.to_scalar(value, enum_name=enum_name, value_map=value_map)
        if scalar is None:
            raise LoqiSerializationError(f"Metadata value for {name!r} cannot be None")
        return LoqiMetadataEntry(name=name, value=scalar)

    def object_metadata(self, entries: dict[str, Any]) -> tuple[LoqiMetadataEntry, ...]:
        return tuple(
            self.metadata_entry(name, value)
            for name, value in entries.items()
            if value is not None
        )

    def localized_metadata(
        self,
        key: str,
        *,
        languages: tuple[str, ...] = ("RU", "EN"),
    ) -> tuple[LoqiMetadataEntry, ...]:
        if self.serializer.locales is None:
            return ()
        entries: list[LoqiMetadataEntry] = []
        for language in languages:
            localized = self.serializer.locales.get(key, language.lower())
            if localized != key:
                entries.append(self.metadata_entry(f"{language}.localizedName", localized))
        return tuple(entries)

    def to_scalar(
        self,
        value: Any,
        *,
        enum_name: str | None = None,
        value_map: dict[Any, str] | None = None,
    ) -> LoqiScalar | None:
        if value is None:
            if enum_name is None:
                raise ValueError("Loqi scalar value cannot be None")
            literal = value_map.get(value, value) if value_map is not None else value
            if not isinstance(literal, str):
                raise LoqiSerializationError(f"Unsupported enum value {value!r} for {enum_name}")
            return self.enum(enum_name, literal)
        if isinstance(value, LoqiEnumLiteral):
            return value
        if isinstance(value, Enum):
            enum_literal = value.value
            if not isinstance(enum_literal, str):
                raise LoqiSerializationError(f"Unsupported enum value {value!r}")
            return self.enum(type(value).__name__, enum_literal)
        if enum_name is not None:
            literal = value_map.get(value, value) if value_map is not None else value
            if not isinstance(literal, str):
                raise LoqiSerializationError(f"Unsupported enum value {value!r} for {enum_name}")
            return self.enum(enum_name, literal)
        if isinstance(value, bool | int | str):
            return value
        raise LoqiSerializationError(f"Unsupported Loqi scalar value {value!r}")

    def property(
        self,
        name: str,
        value: Any,
        *,
        enum_name: str | None = None,
        value_map: dict[Any, str] | None = None,
        metadata: tuple[LoqiMetadataEntry, ...] = (),
    ) -> LoqiProperty:
        return LoqiProperty(
            name=name,
            value=self.to_scalar(value, enum_name=enum_name, value_map=value_map),
            metadata=metadata,
        )

    def relationship(
        self,
        name: str,
        targets: Any,
        *,
        metadata: tuple[LoqiMetadataEntry, ...] = (),
    ) -> RelationshipLink:
        return RelationshipLink(name=name, targets=self.serialize_many(targets), metadata=metadata)

    def relationship_links(
        self,
        name: str,
        targets: Any,
        *,
        metadata: tuple[LoqiMetadataEntry, ...] = (),
    ) -> tuple[RelationshipLink, ...]:
        return tuple(
            RelationshipLink(name=name, targets=(target_ref,), metadata=metadata)
            for target_ref in self.serialize_many(targets)
        )

    def serialize(
        self,
        obj: Any,
        *,
        backlink: tuple[str, LoqiObject] | None = None,
        state_updates: dict[str, Any] | None = None,
    ) -> LoqiObjectRef:
        if obj is None:
            raise LoqiSerializationError("Cannot serialize None as a Loqi object")
        if isinstance(obj, LoqiObjectRef):
            return obj
        ref = self.serializer._serialize_object(obj, self.with_state(**(state_updates or {})))
        if backlink is not None:
            relationship_name, source_object = backlink
            self.serializer._attach_backlink(ref, relationship_name, source_object)
        return ref

    def serialize_many(
        self,
        values: Any,
        *,
        backlink: tuple[str, LoqiObject] | None = None,
        state_updates: dict[str, Any] | None = None,
    ) -> tuple[LoqiObjectRef, ...]:
        if values is None:
            return ()
        if isinstance(values, LoqiObjectRef):
            return (values,)
        if isinstance(values, (list, tuple)):
            return tuple(
                item if isinstance(item, LoqiObjectRef) else self.serialize(item, backlink=backlink, state_updates=state_updates)
                for item in values
                if item is not None
            )
        return (self.serialize(values, backlink=backlink, state_updates=state_updates),)


class LoqiRenderer:
    INDENT = "    "

    def render(self, result: LoqiRenderResult) -> str:
        variables_by_object_id = {
            assignment.object_id: assignment.variable_name
            for assignment in result.variables
        }
        return "\n\n".join(
            self._render_object(loqi_object, variables_by_object_id.get(loqi_object.object_id))
            for loqi_object in result.objects
        )

    def _render_object(self, loqi_object: LoqiObject, variable_name: str | None) -> str:
        declaration = f"obj {loqi_object.object_id} : {loqi_object.type_name} {{"
        if variable_name is not None:
            declaration = f"var {variable_name} = {declaration}"
        lines = [declaration]
        for loqi_property in loqi_object.properties:
            if loqi_property.value is None:
                continue
            line = f"{self.INDENT}{loqi_property.name} = {self._render_scalar(loqi_property.value)}"
            line += self._render_metadata_block(loqi_property.metadata)
            lines.append(line + ";")
        for link in loqi_object.relationship_links:
            if not link.targets:
                continue
            line = f"{self.INDENT}{link.name}({self._render_link_targets(link.targets)})"
            line += self._render_metadata_block(link.metadata)
            lines.append(line + ";")
        lines.append("}" + self._render_metadata_block(tuple(loqi_object.metadata)))
        return "\n".join(lines)

    def _render_link_targets(self, targets: tuple[LoqiObjectRef, ...]) -> str:
        if len(targets) == 1:
            return targets[0].object_id
        return ", ".join(target.object_id for target in targets)

    def _render_scalar(self, value: LoqiScalar | None) -> str:
        if isinstance(value, LoqiEnumLiteral):
            return f"{value.enum_name}:{value.literal}"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            return f'"{escaped}"'
        raise LoqiSerializationError(f"Unsupported rendered scalar value {value!r}")

    def _render_metadata_block(self, metadata: tuple[LoqiMetadataEntry, ...]) -> str:
        if not metadata:
            return ""
        body = " ".join(f"{entry.name} = {self._render_scalar(entry.value)} ;" for entry in metadata)
        return f" [ {body} ]"


class LoqiSerializer:
    def __init__(
        self,
        *,
        adapters_by_type: dict[type[Any], LoqiAdapter[Any]] | None = None,
        locales: Locales | None = None,
    ) -> None:
        self.adapters_by_type = dict(adapters_by_type or build_default_loqi_adapters())
        self.locales = locales
        self.objects: list[LoqiObject] = []
        self._objects_by_python_id: dict[int, tuple[Any, LoqiObject]] = {}
        self._objects_by_id: dict[str, LoqiObject] = {}
        self._object_name_counters: dict[str, int] = {}
        self._variables_by_name: dict[str, str] = {}
        self._variables_by_object_id: dict[str, str] = {}
        self._roots: list[LoqiObjectRef] = []
        self._renderer = LoqiRenderer()

    def serialize(self, root: Any, *, var_name: str | None = None) -> str:
        self._serialize_root(root, var_name=var_name)
        return self._renderer.render(self.render_result())

    def serialize_many(self, roots: Any, *, variables: dict[str, Any] | None = None) -> str:
        for root in roots:
            self._serialize_root(root)
        for variable_name, variable_object in (variables or {}).items():
            self._assign_variable_to_object(variable_object, variable_name)
        return self._renderer.render(self.render_result())

    def render_result(self) -> LoqiRenderResult:
        variables = tuple(
            LoqiVariableAssignment(variable_name=variable_name, object_id=object_id)
            for variable_name, object_id in self._variables_by_name.items()
        )
        return LoqiRenderResult(roots=tuple(self._roots), objects=tuple(self.objects), variables=variables)

    def _serialize_root(self, root: Any, *, var_name: str | None = None) -> LoqiObjectRef:
        ref = self._serialize_object(root, LoqiAdapterContext(serializer=self))
        if var_name is not None:
            self._assign_variable(ref, var_name)
        if ref not in self._roots:
            self._roots.append(ref)
        return ref

    def _assign_variable(self, ref: LoqiObjectRef, var_name: str) -> None:
        if not _is_variable_name(var_name):
            raise LoqiSerializationError(f"Invalid Loqi variable name {var_name!r}")
        loqi_object = self._object_by_ref(ref)
        existing_object_variable = self._variables_by_object_id.get(loqi_object.object_id)
        if existing_object_variable is not None:
            raise LoqiSerializationError(
                f"Loqi object {loqi_object.object_id!r} already has variable "
                f"{existing_object_variable!r}"
            )
        if var_name in self._variables_by_name:
            raise LoqiSerializationError(f"Loqi variable {var_name!r} is already assigned")
        self._variables_by_name[var_name] = loqi_object.object_id
        self._variables_by_object_id[loqi_object.object_id] = var_name

    def _assign_variable_to_object(self, obj: Any, var_name: str) -> None:
        existing = self._objects_by_python_id.get(id(obj))
        if existing is not None:
            self._assign_variable(LoqiObjectRef(existing[1].object_id), var_name)
            return
        self._serialize_root(obj, var_name=var_name)

    def _serialize_object(self, obj: Any, ctx: LoqiAdapterContext) -> LoqiObjectRef:
        existing = self._objects_by_python_id.get(id(obj))
        if existing is not None:
            return LoqiObjectRef(existing[1].object_id)

        adapter = get_loqi_adapter(obj, self.adapters_by_type)
        object_id = self._allocate_object_id(self._adapter_object_name(adapter, obj))
        loqi_object = LoqiObject(object_id=object_id, type_name=adapter.type_name(obj))
        self._objects_by_python_id[id(obj)] = (obj, loqi_object)
        self._objects_by_id[object_id] = loqi_object
        self.objects.append(loqi_object)

        object_ctx = LoqiAdapterContext(serializer=self, current_object=loqi_object, state=dict(ctx.state))
        spec = adapter.describe(obj, object_ctx)
        loqi_object.properties.extend(spec.properties)
        loqi_object.relationship_links.extend(spec.relationship_links)
        loqi_object.metadata.extend(spec.metadata)
        return LoqiObjectRef(object_id)

    def _attach_backlink(self, target_ref: LoqiObjectRef, relationship_name: str, source_object: LoqiObject) -> None:
        target_object = self._object_by_ref(target_ref)
        for link in target_object.relationship_links:
            if link.name != relationship_name:
                continue
            if source_object.object_id in {target.object_id for target in link.targets}:
                return
        target_object.relationship_links.append(
            RelationshipLink(name=relationship_name, targets=(LoqiObjectRef(source_object.object_id),))
        )

    def _object_by_ref(self, ref: LoqiObjectRef) -> LoqiObject:
        try:
            return self._objects_by_id[ref.object_id]
        except KeyError as error:
            raise LoqiSerializationError(f"Unknown Loqi object reference {ref.object_id!r}") from error

    def _allocate_object_id(self, raw_name: str) -> str:
        base_name = _normalize_object_name(raw_name)
        next_index = self._object_name_counters.get(base_name, 0)
        if next_index == 0 and base_name not in self._objects_by_id:
            self._object_name_counters[base_name] = 1
            return base_name

        while True:
            next_index += 1
            candidate = f"{base_name}_{next_index}"
            if candidate not in self._objects_by_id:
                self._object_name_counters[base_name] = next_index
                return candidate

    def _adapter_object_name(self, adapter: LoqiAdapter[Any], obj: Any) -> str:
        object_name: Callable[[Any], str] = getattr(adapter, "object_name", None) # type: ignore
        if callable(object_name):
            return object_name(obj)
        type_name = _normalize_object_name(adapter.type_name(obj))
        next_index = len(self.objects) + 1
        return f"{type_name}_obj_{next_index}"


def get_loqi_adapter(obj: Any, adapters_by_type: dict[type[Any], LoqiAdapter[Any]]) -> LoqiAdapter[Any]:
    obj_type = type(obj)
    adapter = adapters_by_type.get(obj_type)
    if adapter is not None:
        return adapter
    for python_type, registered_adapter in adapters_by_type.items():
        if isinstance(obj, python_type):
            return registered_adapter
    raise LoqiAdapterNotFoundError(f"No Loqi adapter registered for {obj_type.__name__}")


def _normalize_object_name(raw_name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", raw_name.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        return "obj"
    if normalized[0].isdigit():
        return f"obj_{normalized}"
    return normalized


def _is_variable_name(name: str) -> bool:
    return re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name) is not None


def serialize_loqi(
    root: Any,
    *,
    adapters_by_type: dict[type[Any], LoqiAdapter[Any]] | None = None,
    locales: Locales | None = None,
    var_name: str | None = None,
) -> str:
    return LoqiSerializer(adapters_by_type=adapters_by_type, locales=locales).serialize(root, var_name=var_name)


def build_default_loqi_adapters() -> dict[type[Any], LoqiAdapter[Any]]:
    from src.serialization.adapters.rules import build_rules_loqi_adapters

    return build_rules_loqi_adapters()


__all__ = [
    "LoqiAdapter",
    "LoqiAdapterContext",
    "LoqiAdapterNotFoundError",
    "LoqiDomainMismatchError",
    "LoqiEnumLiteral",
    "LoqiMetadataEntry",
    "LoqiObject",
    "LoqiObjectRef",
    "LoqiObjectSpec",
    "LoqiProperty",
    "LoqiRenderResult",
    "LoqiRenderer",
    "LoqiSerializationError",
    "LoqiSerializer",
    "LoqiVariableAssignment",
    "RelationshipLink",
    "build_default_loqi_adapters",
    "get_loqi_adapter",
    "serialize_loqi",
]
