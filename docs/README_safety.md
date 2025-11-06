# Безопасность визуализации CFG

Модуль `cfg_visualizer.py` теперь безопасно обрабатывает неполные и повреждённые графы потока управления.

## Проблемы, которые решены

### 1. Висячие рёбра (Orphan Edges)
**Проблема**: Рёбра, которые ссылаются на несуществующие узлы.
```
Edge BEGIN_206 -> BEGIN_209 (missing dst)
Edge END_210 -> END_207 (missing src)
```

**Решение**: 
- Проверка существования узлов перед добавлением рёбер в NetworkX
- Пропуск висячих рёбер с предупреждением
- Диагностика проблемных рёбер

### 2. Отсутствующие поля в узлах
**Проблема**: `KeyError: 'node_obj'` при обращении к несуществующим полям.

**Решение**:
- Безопасное получение полей через `.get()`
- Fallback значения для отсутствующих данных
- Защита от `None` значений

### 3. Отключённые узлы
**Проблема**: Узлы, не связанные с остальным графом.

**Решение**:
- Диагностика отключённых узлов
- Корректная визуализация изолированных компонентов

## Новые функции безопасности

### `diagnose_cfg(cfg: CFG) -> dict`
Диагностирует проблемы в CFG:
```python
issues = diagnose_cfg(cfg)
print(f"Orphan edges: {len(issues['orphan_edges'])}")
print(f"Disconnected nodes: {issues['disconnected_nodes']}")
print(f"Missing nodes: {list(issues['missing_nodes'])}")
```

### Безопасное построение NetworkX графа
```python
def _build_networkx_graph(cfg: CFG) -> nx.DiGraph:
    # Проверяет существование узлов перед добавлением рёбер
    if edge.src in cfg.nodes and edge.dst in cfg.nodes:
        G.add_edge(edge.src, edge.dst, ...)
    else:
        print(f"Warning: Skipping edge {edge.src} -> {edge.dst}")
```

### Защищённая визуализация
```python
# Безопасное получение node_obj
node_obj = G.nodes[node_id].get('node_obj')
if node_obj:
    node_colors.append(_get_node_color(node_obj))
else:
    node_colors.append("lightgray")  # Fallback
```

## Диагностические сообщения

Визуализатор теперь выводит подробную диагностику:

```
Warning: Found 2 orphan edges in CFG:
  Edge BEGIN_206 -> BEGIN_209 (missing dst)
  Edge END_210 -> END_207 (missing src)
Warning: Found 2 disconnected nodes: ['BEGIN_194', 'END_195']
Warning: Missing nodes referenced in edges: ['END_210', 'BEGIN_209']
CFG stats: 10 nodes, 10 edges
```

## Тестирование безопасности

Создан специальный тест `test/test_cfg_visualizer_safety.py`:

- **Висячие рёбра**: Тестирует обработку рёбер с несуществующими узлами
- **Пустой CFG**: Тестирует обработку пустых графов
- **Отключённые узлы**: Тестирует изолированные компоненты
- **Повреждённые данные**: Тестирует отсутствующие поля
- **Большое количество проблем**: Тестирует производительность

## Результат

✅ **Визуализация теперь работает стабильно** даже с неполными CFG
✅ **Подробная диагностика** помогает выявить проблемы в построении CFG
✅ **Graceful degradation** - визуализация продолжает работать с доступными данными
✅ **Полное тестирование** всех сценариев ошибок

## Использование

```python
from src.cfg.cfg_visualizer import visualize_cfg, diagnose_cfg

# Диагностика проблем
issues = diagnose_cfg(cfg)
if issues['orphan_edges']:
    print("CFG has problems, but visualization will work")

# Безопасная визуализация
output_file = visualize_cfg(cfg, "output.png")
# Всегда создаёт файл, даже с проблемными данными
```
