"""
Универсальный поиск в JSON/AST данных с поддержкой поиска в глубину и в ширину.
"""

from collections import deque
from collections.abc import Callable
from typing import Any, Literal, overload

type PathItem = str | int
type JSONPath = tuple[PathItem, ...]

_MISSING = object()


def _iter_children(node: Any) -> list[tuple[PathItem, Any]]:
    if isinstance(node, dict):
        return list(node.items())
    if isinstance(node, list):
        return list(enumerate(node))
    return []


@overload
def _search_dfs_impl(
    data: Any,
    predicate: Callable[[Any], bool],
    max_results: int | None = None,
    *,
    with_paths: Literal[False] = False,
) -> list[Any]: ...


@overload
def _search_dfs_impl(
    data: Any,
    predicate: Callable[[Any], bool],
    max_results: int | None = None,
    *,
    with_paths: Literal[True],
) -> list[tuple[JSONPath, Any]]: ...


def _search_dfs_impl(
    data: Any,
    predicate: Callable[[Any], bool],
    max_results: int | None = None,
    *,
    with_paths: bool = False,
) -> list[Any] | list[tuple[JSONPath, Any]]:
    results: list[Any] | list[tuple[JSONPath, Any]] = []

    def _search_recursive(node: Any, current_path: JSONPath = ()) -> bool:
        for step, child in _iter_children(node):
            if _search_recursive(child, current_path + (step,)):
                return True

        # Postorder DFS: сначала дочерние узлы, затем текущий.
        if predicate(node):
            if with_paths:
                results.append((current_path, node))
            else:
                results.append(node)
            if max_results is not None and len(results) >= max_results:
                return True

        return False

    _search_recursive(data)
    return results


def search_dfs(data: Any, predicate: Callable[[Any], bool], max_results: int | None = None) -> list[Any]:
    """
    Поиск в глубину с предикатом.

    Возвращает результаты от самых глубоких к самым верхним, слева направо,
    имитируя порядок вычисления операндов в выражении.

    Args:
        data: JSON данные (dict, list, примитивы)
        predicate: Функция предикат callable(node) -> bool
        max_results: Максимальное количество результатов (None = без ограничений)

    Returns:
        List найденных узлов в порядке от самых глубоких к верхним
    """
    return _search_dfs_impl(data, predicate, max_results=max_results, with_paths=False)


def search_bfs(data: Any, predicate: Callable[[Any], bool], max_results: int | None = None) -> list[Any]:
    """
    Поиск в ширину с предикатом.

    Сначала проверяет узлы на текущем уровне, затем переходит к следующему.

    Args:
        data: JSON данные (dict, list, примитивы)
        predicate: Функция предикат callable(node) -> bool
        max_results: Максимальное количество результатов (None = без ограничений)

    Returns:
        List найденных узлов в порядке обхода в ширину
    """
    results = []
    queue = deque([data])

    while queue and (max_results is None or len(results) < max_results):
        current_node = queue.popleft()

        if predicate(current_node):
            results.append(current_node)
            if max_results is not None and len(results) >= max_results:
                break

        for _, child in _iter_children(current_node):
            queue.append(child)

    return results


def search_with_paths_dfs(
    data: Any,
    predicate: Callable[[Any], bool],
    max_results: int | None = None,
) -> list[tuple[JSONPath, Any]]:
    """
    Поиск в глубину с возвращением путей к найденным узлам.

    Args:
        data: JSON данные (dict, list, примитивы)
        predicate: Функция предикат callable(node) -> bool
        max_results: Максимальное количество результатов (None = без ограничений)

    Returns:
        List кортежей (path, node), где path - tuple ключей/индексов для доступа к узлу
    """
    return _search_dfs_impl(data, predicate, max_results=max_results, with_paths=True)


def get_node_by_path(data: Any, path: JSONPath, default: Any = _MISSING) -> Any:
    """
    Получить узел по пути в JSON данных.

    Args:
        data: JSON данные
        path: Путь к узлу (tuple ключей/индексов)
        default: Значение, возвращаемое если путь не найден. Если не передано, возвращается None.

    Returns:
        Узел по указанному пути или default/None если путь не найден
    """
    current = data
    for step in path:
        if isinstance(current, dict) and step in current:
            current = current[step]
        elif isinstance(current, list) and isinstance(step, int):
            if 0 <= step < len(current):
                current = current[step]
            else:
                return None if default is _MISSING else default
        else:
            return None if default is _MISSING else default
    return current
