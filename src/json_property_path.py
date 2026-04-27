"""
Навигация по JSON-структурам с помощью mini-language `property_path`.

Модуль не зависит от CFG и AST wrapper и работает только с обычными JSON-подобными
структурами Python: dict, list и примитивами.

Mini-language `property_path`:
- Компоненты разделяются символом `/`, пробелы вокруг компонентов игнорируются.
- `name` - переход к ключу словаря `name`.
- `[N]` - переход к элементу списка по индексу `N`, где `N >= 0`.
- `^` - переход к родительскому узлу относительно текущего пути.
- `[next]` - переход к следующему соседнему элементу списка.

Семантика:
- Путь вычисляется относительно `current_path`.
- Если `origin="previous"`, путь вычисляется относительно `previous_path`.
- Пустой путь, невалидный индекс или невозможная навигация возвращают `None`.
- Возвращается и найденное значение, и его точный путь как `tuple[str | int, ...]`.

Ограничения:
- Язык не поддерживает экранирование ключей.
- Ключи JSON, содержащие служебные формы вроде `/`, `^`, `[next]`, `[0]`, неразличимы с операторами языка.
"""

from dataclasses import dataclass
from typing import Any

from src.json_search import JSONPath, get_node_by_path, search_with_paths_dfs


@dataclass(frozen=True)
class ResolvedJSONPath:
    path: JSONPath
    value: Any


def parse_property_path(property_path: str | None) -> tuple[str, ...] | None:
    """
    Нормализует property_path и разбивает его на компоненты.
    """
    if property_path is None:
        return None
    components = tuple(component.strip() for component in property_path.split("/") if component.strip())
    if not components:
        return None
    return components


def resolve_json_property_path(
    data: Any,
    property_path: str,
    *,
    current_path: JSONPath = (),
    previous_path: JSONPath | None = None,
    origin: str | None = None,
) -> ResolvedJSONPath | None:
    """
    Разрешает property_path относительно JSON-дерева и текущего узла.

    Args:
        data: Корневой JSON-объект.
        property_path: Строка mini-language.
        current_path: Путь к текущему узлу.
        previous_path: Путь к предыдущему узлу, используется с origin='previous'.
        origin: Если равно 'previous', путь вычисляется относительно previous_path.

    Returns:
        ResolvedJSONPath или None, если путь не удалось разрешить.
    """
    components = parse_property_path(property_path)
    if components is None:
        return None

    base_path = previous_path if origin == "previous" else current_path
    if base_path is None:
        return None

    resolved_path = _resolve_components(data, base_path, components)
    if resolved_path is None:
        return None

    missing = object()
    value = get_node_by_path(data, resolved_path, default=missing)
    if value is missing:
        return None

    return ResolvedJSONPath(path=resolved_path, value=value)


def get_json_by_property_path(
    data: Any,
    property_path: str,
    *,
    current_path: JSONPath = (),
    previous_path: JSONPath | None = None,
    origin: str | None = None,
    default: Any = None,
) -> Any:
    """
    Упрощённый helper: возвращает только значение по property_path.
    """
    resolved = resolve_json_property_path(
        data,
        property_path,
        current_path=current_path,
        previous_path=previous_path,
        origin=origin,
    )
    if resolved is None:
        return default
    return resolved.value


def find_json_path_to_object(data: Any, target: Any) -> JSONPath | None:
    """
    Возвращает путь к конкретному объекту внутри JSON-дерева.

    Поиск выполняется по идентичности объекта (`is`), а не по равенству (`==`),
    чтобы одинаковые по значению узлы не становились неоднозначными.
    """
    matches = search_with_paths_dfs(data, lambda node: node is target, max_results=1)
    if not matches:
        return None
    path, _ = matches[0]
    return path


def _resolve_components(data: Any, start_path: JSONPath, components: tuple[str, ...]) -> JSONPath | None:
    current_path = start_path

    for component in components:
        current_value = get_node_by_path(data, current_path, default=_MISSING)
        if current_value is _MISSING:
            return None

        next_path = _resolve_component(data, current_path, current_value, component)
        if next_path is None:
            return None
        current_path = next_path

    return current_path


def _resolve_component(data: Any, current_path: JSONPath, current_value: Any, component: str) -> JSONPath | None:
    if component == "^":
        if not current_path:
            return None
        return current_path[:-1]

    if component == "[next]":
        if not current_path:
            return None
        parent_path = current_path[:-1]
        last_step = current_path[-1]
        parent_value = get_node_by_path(data, parent_path, default=_MISSING)
        if parent_value is _MISSING or not isinstance(parent_value, list) or not isinstance(last_step, int):
            return None
        next_index = last_step + 1
        if next_index >= len(parent_value):
            return None
        return parent_path + (next_index,)

    if _is_list_index_component(component):
        index = int(component[1:-1].strip())
        if not isinstance(current_value, list):
            return None
        if not 0 <= index < len(current_value):
            return None
        return current_path + (index,)

    if isinstance(current_value, dict) and component in current_value:
        return current_path + (component,)

    return None


def _is_list_index_component(component: str) -> bool:
    if not (component.startswith("[") and component.endswith("]")):
        return False
    inner = component[1:-1].strip()
    return inner.isdigit()


_MISSING = object()
