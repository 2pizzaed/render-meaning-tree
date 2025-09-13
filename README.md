# render-meaning-tree

**render-meaning-tree** — это расширение для проекта [meaning_tree](https://github.com/2pizzaed/meaning_tree), позволяющее преобразовать абстрактное смысловое дерево сразу в наглядный HTML‑интерфейс. В основе визуализации лежит класс StatementFact из репозитория [CompPrehension](https://github.com/CompPrehension/CompPrehension), который собирает детальную информацию о каждом операторе (statement) в дереве.

---

## Требования

- `Java 21+`
- [`uv`](https://github.com/astral-sh/uv)
- `make`

## Установка

```bash
# 0. Склонируйте репозиторий
git clone --recurse-submodules -j8 https://github.com/2pizzaed/render-meaning-tree.git
cd render-meaning-tree

# 1. Сборка core‑модуля meaning_tree
make mt

# 2. Генерация HTML‑визуализации AST
make run

# 3. Запуск тестов
make test
```

---

## Запуск:

```bash
uv run main.py \
  --file examples/Sample.java \
  --output result          \
  --cfg                    \
  --analyze
```

**Опции:**
- `-f, --file` - путь до файла с исходным кодом
- `-c, --code "<строка кода>"` - обработать код из переданной строки вместо файла
- `-o, --output <имя>` - имя выходного `.html` файла, по умолчанию `result`
- `-g, --cfg` - сгенерировать и сохранить граф потока управления (Control Flow Graph)
- `-a, --analyze` - вывести в консоль статистику: количество базовых блоков, редуцируемость, количество заголовков циклов, обратных и критических рёбер и т. д.

### Пример
```bash
uv run main.py -c "a = 10; if (b > 10) { a = b; c = 10; }"
```
В результате в файл `result.html` сохраняется графическое представление данного фрагмента кода, а в консоль выводится следующая информация:
```python
CompPrehensionQuestion(type='',
                       name='',
                       statement_facts=[StatementFact(subject_id=19,
                                                      subject_type='program_entry_point',
                                                      verb='parent_of',
                                                      object_id=4,
                                                      object_type='assignment_statement'),
                                        StatementFact(subject_id=19,
                                                      subject_type='program_entry_point',
                                                      verb='parent_of',
                                                      object_id=17,
                                                      object_type='if_statement'),
                                        StatementFact(subject_id=4,
                                                      subject_type='assignment_statement',
                                                      verb='next_sibling',
                                                      object_id=17,
                                                      object_type='if_statement'),
                                        StatementFact(subject_id=17,
                                                      subject_type='if_statement',
                                                      verb='branches_item',
                                                      object_id=18,
                                                      object_type='condition_branch')])
```

### Пример с глубокой вложенностью
```bash
python  main.py -c "a = 10; if (b > 10) if (X) if (Y) if (Z) if (W) if (N) if(M) { a = b; c = 10; }"
````

---

## Архитектура

Проект построен по принципу разделения на два основных слоя: ядро анализа и парсинга (Java, папка `meaning_tree/`) и слой визуализации и инструментов (Python, папка `src/` и основной скрипт `main.py`). Взаимодействие между слоями происходит через сериализацию AST в JSON/словарь и дальнейшую обработку в Python.

### Ядро анализа и парсинга (Java, `meaning_tree/`)
- **Парсер и AST:** В директории `meaning_tree/` реализованы парсер исходного кода (Java, Python, C++ и др.) и построение абстрактного синтаксического дерева (AST). Каждый язык поддерживается отдельным модулем (`languages/java/JavaLanguage.java`, `languages/python/PythonLanguage.java` и т.д.).
- **Узлы AST:** Для каждого типа синтаксической конструкции реализован свой класс-узел (например, `nodes/expressions/BinaryExpression.java`, `nodes/statements/CompoundStatement.java`).
- **Сериализация:** AST сериализуется в JSON или структуру, пригодную для передачи в Python.
- **Расширяемость:** Для добавления нового языка или конструкции достаточно реализовать соответствующий класс и зарегистрировать его в фабрике парсера.

### Слой визуализации и инструментов (Python, `src/`, `main.py`)
- **Рендеринг AST:** Модуль `src/renderer.py` содержит класс `Renderer`, который с помощью декоратора `@r.node(type=...)` регистрирует функции-обработчики для разных типов AST-узлов. Это позволяет гибко наращивать поддержку новых конструкций без изменения основной логики.
- **Генерация HTML:** Для визуализации используется Jinja2 и шаблоны из папки `templates/`. Каждый узел AST преобразуется в HTML с подсветкой синтаксиса и разметкой по шаблону.
- **Генерация CFG:** Модуль `src/cfg.py` строит граф потока управления (Control Flow Graph) на основе AST и может визуализировать его в PNG.
- **Сериализация и отладка:** Модули в `src/serializers/` позволяют сериализовать AST для отладки или интеграции с внешними инструментами.

### Взаимодействие компонентов
1. Пользователь запускает `main.py`, передавая исходный код или файл.
2. Код парсится Java-модулем, AST сериализуется и передаётся в Python.
3. Python-слой визуализирует AST, строит HTML и (опционально) CFG.
4. Результаты сохраняются в виде HTML-файла и/или PNG-графа.
