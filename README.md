# render-meaning-tree

**render-meaning-tree** — это расширение для проекта meaning_tree, позволяющее преобразовать ваше JSON‑представление абстрактного синтаксического дерева сразу в наглядный HTML‑интерфейс. В основе визуализации лежит класс StatementFact из репозитория [CompPrehension](https://github.com/CompPrehension/CompPrehension), который собирает детальную информацию о каждом операторе (statement) в дереве.

---

## Требования

- `Java 21+`
- [`uv`](https://github.com/astral-sh/uv)
- `make`

## Установка

```bash
# 0. Склонируйте репозиторий
git clone --recurse-submodules -j8 https://github.com/samedit66/render-meaning-tree.git
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
