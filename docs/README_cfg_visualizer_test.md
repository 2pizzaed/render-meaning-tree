# Тест модуля визуализации CFG

Файл `test_cfg_visualizer.py` содержит комплексные тесты для модуля `src/cfg/cfg_visualizer.py`.

## Что тестируется

### 1. Создание меток узлов (`test_create_node_label`)
- BEGIN и END узлы
- Обычные узлы с kind и role
- Узлы с AST ID в metadata

### 2. Создание меток рёбер (`test_create_edge_label`)
- Рёбра без constraints
- Рёбра с `condition_value=True` (отображается как "T")
- Рёбра с `condition_value=False` (отображается как "F")

### 3. Конвертация в NetworkX (`test_build_networkx_graph`)
- Правильное добавление всех узлов
- Правильное добавление всех рёбер
- Сохранение меток узлов и рёбер

### 4. Базовая визуализация (`test_visualize_cfg_basic`)
- Создание файла изображения
- Проверка размера файла

### 5. Визуализация с constraints (`test_visualize_cfg_with_constraints`)
- CFG с рёбрами, содержащими constraints
- Проверка корректности отображения меток

### 6. Визуализация из AST (`test_visualize_cfg_from_ast`)
- **Главный тест**: Воспроизводит процесс создания `example_cfg.png`
- Создаёт AST с if_statement и вложенными структурами
- Проверяет создание CFG с 26 узлами и 26 рёбрами
- Проверяет размер результирующего файла (>100KB)

### 7. Разные layout (`test_visualize_cfg_different_layouts`)
- Spring layout (по умолчанию)
- Hierarchical layout (требует graphviz)

### 8. Пустой CFG (`test_visualize_empty_cfg`)
- Обработка CFG только с BEGIN и END узлами

### 9. Большой CFG (`test_visualize_cfg_large`)
- CFG с множеством узлов и сложной структурой рёбер
- Проверка производительности и качества визуализации

## Исходный AST для теста

Тест использует следующий AST (абстрактное синтаксическое дерево):

```python
{
    "type": "program_entry_point",
    "id": 1,
    "body": [
        {
            "type": "if_statement", 
            "id": 2,
            "branches": [
                {
                    "type": "if_branch",
                    "condition": {"type": "condition", "id": 3},
                    "body": {
                        "type": "compound_statement",
                        "id": 4,
                        "statements": [
                            {"type": "assignment_statement", "id": 5}
                        ]
                    }
                }
            ],
            "elseBranch": {
                "type": "compound_statement",
                "id": 6,
                "statements": [
                    {"type": "assignment_statement", "id": 7}
                ]
            }
        }
    ]
}
```

## Структура AST:
```
program_entry_point (id: 1)
└── if_statement (id: 2)
    ├── if_branch
    │   ├── condition (id: 3)
    │   └── compound_statement (id: 4)
    │       └── assignment_statement (id: 5)
    └── elseBranch
        └── compound_statement (id: 6)
            └── assignment_statement (id: 7)
```

## Запуск тестов

```bash
# Запуск всех тестов
python test/test_cfg_visualizer.py

# Запуск через unittest
python -m unittest test.test_cfg_visualizer.TestCFGVisualizer

# Запуск конкретного теста
python -m unittest test.test_cfg_visualizer.TestCFGVisualizer.test_visualize_cfg_from_ast
```

## Ожидаемые результаты

- Все 9 тестов должны пройти успешно
- Файлы визуализации создаются во временных директориях
- Размер файла `test_from_ast.png` должен быть ~638KB (как в `example_cfg.png`)
- CFG должен содержать 26 узлов и 26 рёбер

## Примечания

- Тест использует временные директории для изоляции
- Автоматическая очистка после каждого теста
- Совместимость с Windows (без Unicode символов в выводе)
- Проверка как функциональности, так и качества визуализации
