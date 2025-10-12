"""
Универсальный поиск в JSON/AST данных с поддержкой поиска в глубину и в ширину.
"""

from typing import Any, Callable, Optional


def search_dfs(data: Any, predicate: Callable[[Any], bool], max_results: Optional[int] = None) -> list[Any]:
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
    results = []
    
    def _search_recursive(node: Any, current_path: list[str] = None) -> None:
        if current_path is None:
            current_path = []
            
        # Проверяем предикат для текущего узла
        if predicate(node):
            results.append(node)
            if max_results and len(results) >= max_results:
                return
        
        # Рекурсивно обходим дочерние узлы
        if isinstance(node, dict):
            for key, value in node.items():
                _search_recursive(value, current_path + [key])
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _search_recursive(item, current_path + [str(i)])
    
    _search_recursive(data)
    return results


def search_bfs(data: Any, predicate: Callable[[Any], bool], max_results: Optional[int] = None) -> list[Any]:
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
    queue = [data]
    
    while queue and (max_results is None or len(results) < max_results):
        current_node = queue.pop(0)
        
        # Проверяем предикат для текущего узла
        if predicate(current_node):
            results.append(current_node)
        
        # Добавляем дочерние узлы в очередь
        if isinstance(current_node, dict):
            queue.extend(current_node.values())
        elif isinstance(current_node, list):
            queue.extend(current_node)
    
    return results


def search_with_paths_dfs(data: Any, predicate: Callable[[Any], bool], max_results: Optional[int] = None) -> list[tuple[list[str], Any]]:
    """
    Поиск в глубину с возвращением путей к найденным узлам.
    
    Args:
        data: JSON данные (dict, list, примитивы)
        predicate: Функция предикат callable(node) -> bool
        max_results: Максимальное количество результатов (None = без ограничений)
    
    Returns:
        List кортежей (path, node), где path - список ключей/индексов для доступа к узлу
    """
    results = []
    
    def _search_recursive(node: Any, current_path: list[str] = None) -> None:
        if current_path is None:
            current_path = []
            
        # Проверяем предикат для текущего узла
        if predicate(node):
            results.append((current_path.copy(), node))
            if max_results and len(results) >= max_results:
                return
        
        # Рекурсивно обходим дочерние узлы
        if isinstance(node, dict):
            for key, value in node.items():
                _search_recursive(value, current_path + [key])
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _search_recursive(item, current_path + [str(i)])
    
    _search_recursive(data)
    return results


def get_node_by_path(data: Any, path: list[str]) -> Any:
    """
    Получить узел по пути в JSON данных.
    
    Args:
        data: JSON данные
        path: Путь к узлу (список ключей/индексов)
    
    Returns:
        Узел по указанному пути или None если путь не найден
    """
    current = data
    for step in path:
        if isinstance(current, dict) and step in current:
            current = current[step]
        elif isinstance(current, list) and step.isdigit():
            index = int(step)
            if 0 <= index < len(current):
                current = current[index]
            else:
                return None
        else:
            return None
    return current
