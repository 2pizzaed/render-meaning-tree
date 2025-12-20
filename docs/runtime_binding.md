# Связывание Runtime Событий с Трассами Выполнения

## Обзор

Система связывания runtime событий обеспечивает привязку данных реального выполнения программы (аргументы функций, возвращаемые значения, значения условий) к статическим трассам выполнения, построенным на основе CFG (Control Flow Graph).

## Архитектура системы

### Два этапа работы

#### 1. Первичный анализ выражения (создание сценария)

**Цель:** Собрать информацию о реальном выполнении программы и создать сценарий.

**Процесс:**
1. Выполнение кода с трассировкой:
   ```python
   from src.runtime import execute_with_trace
   
   runtime_trace = execute_with_trace(
       source_code,
       track_conditions=True,  # Включает захват значений условий
       line_to_ast_id=line_to_ast_id  # Маппинг для корректных ast_id
   )
   ```

2. Создание сценария из RuntimeTrace:
   ```python
   from src.runtime.scenario_exporter import build_condition_sequences_from_trace
   
   # Создаём condition_sequences для TraceScenarioConfig
   condition_sequences = build_condition_sequences_from_trace(runtime_trace)
   
   scenario_config = TraceScenarioConfig(
       name="from_runtime",
       condition_sequences=condition_sequences
   )
   ```

**Результат:** 
- `RuntimeTrace` со всеми событиями (вызовы, возвраты, условия, print)
- `TraceScenarioConfig` с последовательностями значений условий

**Важно:** 
- Все события фиксируются в порядке выполнения (поле `order`)
- Все возвраты фиксируются, включая `None`
- Условия группируются по `ast_id` в порядке вычисления

#### 2. Повторная генерация с имеющимся сценарием (построение трассы)

**Цель:** Построить трассу выполнения на основе сценария и привязать runtime значения.

**Процесс:**
1. Построение трассы из CFG по сценарию:
   ```python
   from src.cfg.trace_builder import generate_trace_variants
   
   trace_results = generate_trace_variants(cfg, [scenario_config])
   trace_acts = trace_results[0].trace_acts
   ```

2. Обогащение трассы runtime значениями:
   ```python
   from src.runtime.matcher import enrich_trace_with_runtime
   
   enriched_trace = enrich_trace_with_runtime(
       trace_acts,
       runtime_trace,  # Тот же RuntimeTrace из первого этапа
       ast_analyzer
   )
   ```

**Результат:**
- Трасса выполнения (`list[TraceAct]`) с заполненными полями:
  - `runtime_info.function_args` - аргументы вызовов функций
  - `runtime_info.return_value` - возвращаемые значения (None не отображается)
  - `condition_value` - значения условий (OptionalBoolValue)

## Стратегия последовательного связывания

### Принципы работы

Система использует **последовательное связывание** для достижения 100% надежности:

1. **Последовательный проход по трассе:**
   - Трасса обрабатывается от начала до конца (по порядку актов в `trace_acts`)
   - Для каждого акта определяется, требуется ли для него runtime событие

2. **Последовательное извлечение событий:**
   - События из `RuntimeTrace` уже упорядочены по времени выполнения (поле `order`)
   - При требовании значения запрашивается следующее неиспользованное событие соответствующего типа
   - События помечаются как использованные после привязки

3. **Строгая валидация:**
   - Проверяется соответствие типа события ожидаемому
   - Проверяется соответствие параметров (имя функции, ast_id для условий)
   - При несоответствии выбрасывается исключение

### Типы связываемых событий

#### 1. Вызовы функций (BEGIN)

**Требование:** Аргументы при вызове функции прицепляются к началу (BEGIN) вызова функции.

**Реализация:**
- Класс: `BindableFunctionCall`
- Соответствие: BEGIN-акт функции с соответствующим именем
- Привязка: `act.runtime_info.function_args = call.local_vars`

**Пример:**
```python
# BEGIN акт функции factorial
# → BindableFunctionCall с function_name="factorial"
# → Привязка: runtime_info.function_args = {"n": 5}
```

#### 2. Возвращаемые значения (END)

**Требование:** Возвращаемое значение функции прицепляется к окончанию (END) вызова функции. None не отображается.

**Реализация:**
- Класс: `BindableFunctionReturn`
- Соответствие: END-акт функции с соответствующим именем
- Привязка: `act.runtime_info.return_value = ret.return_value` (только если не None)

**Особенности:**
- Все возвраты фиксируются в RuntimeTrace (включая None)
- При связывании: если `return_value is None`, значение не присваивается в `runtime_info`
- Событие возврата валидируется, даже если значение None

**Пример:**
```python
# END акт функции factorial
# → BindableFunctionReturn с function_name="factorial", return_value=120
# → Привязка: runtime_info.return_value = 120

# Если return_value=None:
# → Событие валидируется, но runtime_info.return_value не устанавливается
```

#### 3. Значения условий (ATOM с role=condition)

**Требование:** Значение управляющего условия прицепляется к оператору expr с ролью условия (condition) -- (ATOM).

**Реализация:**
- Класс: `BindableConditionEvaluation`
- Соответствие: ATOM-акт с `cfg_node.is_condition() == True` и соответствующим `ast_id`
- Привязка: `act.condition_value = OptionalBoolValue.true/false`

**Особенности:**
- Используется `ast_id` для точного сопоставления
- Значения преобразуются из `bool` в `OptionalBoolValue`

**Пример:**
```python
# ATOM акт с условием (if n <= 1)
# → BindableConditionEvaluation с ast_id=42, value=False
# → Привязка: condition_value = OptionalBoolValue.false
```

## Классы и функции

### BindableEvent и подклассы

**Расположение:** `src/runtime/bindable_events.py`

**Базовый класс:**
```python
class BindableEvent:
    event: RuntimeEvent
    used: bool = False
    
    def matches(act: TraceAct) -> bool
    def validate_match(act: TraceAct) -> None
    def mark_used() -> None
```

**Подклассы:**
- `BindableFunctionCall` - для вызовов функций
- `BindableFunctionReturn` - для возвратов
- `BindableConditionEvaluation` - для условий

**Создание списка:**
```python
from src.runtime.bindable_events import create_bindable_events

bindable_events = create_bindable_events(runtime_trace.events)
```

### Основная функция связывания

**Расположение:** `src/runtime/matcher.py`

```python
def enrich_trace_with_runtime(
    trace_acts: list[TraceAct],
    runtime_trace: RuntimeTrace,
    ast_analyzer: ASTNodeAnalyzer,
) -> list[TraceAct]
```

**Алгоритм:**
1. Создаёт список `BindableEvent` из `runtime_trace.events`
2. Последовательно проходит по `trace_acts`
3. Для каждого акта:
   - Определяет требуемый тип события (`_get_required_event_type`)
   - Находит следующее неиспользованное событие (`_find_next_unused_event`)
   - Валидирует соответствие (`validate_match`)
   - Привязывает событие к акту (`_bind_event_to_act`)
   - Помечает событие как использованное

**Обработка ошибок:**
- `RuntimeError`: требуемое событие отсутствует в runtime trace
- `ValueError`: событие не соответствует ожидаемому акту

## Обработка особых случаев

### Рекурсия

Последовательное связывание корректно обрабатывает рекурсивные вызовы:
- События упорядочены по времени выполнения
- Каждое событие используется только один раз
- Имя функции используется для валидации соответствия

**Пример:**
```python
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

# RuntimeTrace содержит:
# 1. CALL factorial(n=5)
# 2. CALL factorial(n=4)
# 3. CALL factorial(n=3)
# 4. RETURN factorial -> 1
# 5. RETURN factorial -> 2
# 6. RETURN factorial -> 6
# 7. RETURN factorial -> 24
# 8. RETURN factorial -> 120

# Связывание происходит последовательно:
# BEGIN factorial(5) → CALL #1
# BEGIN factorial(4) → CALL #2
# BEGIN factorial(3) → CALL #3
# END factorial(3) → RETURN #4
# END factorial(4) → RETURN #5
# END factorial(5) → RETURN #8
```

### Циклы

Циклы обрабатываются аналогично:
- Условия цикла вычисляются на каждой итерации
- События условий упорядочены по времени выполнения
- Связывание происходит последовательно по порядку в трассе

### None для return

**Требование:** None не отображается в runtime_info.

**Реализация:**
```python
# В _bind_event_to_act:
if ret.return_value is not None:
    act.runtime_info.return_value = ret.return_value
# Если None - не присваиваем, но событие валидируется
```

**Важно:** Все возвраты (включая None) должны быть зафиксированы в RuntimeTrace для строгой валидации.

## Надежность связывания

### Цель: 100% надежность

**Достигается через:**
1. Последовательный проход по трассе (исключает пропуски)
2. Последовательное извлечение событий (исключает повторное использование)
3. Строгую валидацию соответствия (обнаруживает ошибки)
4. Использование `ast_id` для условий (точное сопоставление)
5. Использование имени функции для вызовов/возвратов

### Условия достижения 100% надежности

1. **RuntimeTrace должен содержать все события:**
   - Все вызовы функций
   - Все возвраты (включая None)
   - Все вычисления условий
   - В правильном порядке выполнения

2. **Трасса должна соответствовать RuntimeTrace:**
   - Порядок актов должен соответствовать порядку событий
   - Количество вызовов/возвратов должно совпадать
   - Количество условий должно совпадать

3. **Корректные ast_id:**
   - Для условий должны быть корректные `ast_id` из meaning-tree
   - Маппинг `line_to_ast_id` должен быть построен правильно

### Обнаружение ошибок

Система выбрасывает исключения при:
- Отсутствии требуемого события в RuntimeTrace
- Несоответствии типа события ожидаемому
- Несоответствии параметров (имя функции, ast_id)

Это позволяет обнаружить ошибки построения сценария на раннем этапе.

## Примеры использования

### Полный цикл работы

```python
from src.runtime import execute_with_trace
from src.runtime.scenario_exporter import build_condition_sequences_from_trace
from src.cfg.trace_builder import generate_trace_variants, TraceScenarioConfig
from src.runtime.matcher import enrich_trace_with_runtime

# 1. Первичный анализ - создание сценария
runtime_trace = execute_with_trace(
    source_code,
    track_conditions=True,
    line_to_ast_id=line_to_ast_id
)

condition_sequences = build_condition_sequences_from_trace(runtime_trace)
scenario = TraceScenarioConfig(
    name="from_runtime",
    condition_sequences=condition_sequences
)

# 2. Повторная генерация - построение трассы
trace_results = generate_trace_variants(cfg, [scenario])
trace_acts = trace_results[0].trace_acts

# 3. Обогащение runtime значениями
enriched_trace = enrich_trace_with_runtime(
    trace_acts,
    runtime_trace,  # Тот же RuntimeTrace
    ast_analyzer
)
```

### Удобная функция

```python
from src.runtime.matcher import enrich_single_scenario

# Выполняет код и обогащает трассу в один вызов
enriched_trace = enrich_single_scenario(
    trace_acts,
    source_code,
    filename,
    ast_analyzer
)
```

## Расширяемость

Система спроектирована для будущего расширения:

1. **Добавление новых типов событий:**
   - Создать подкласс `BindableEvent`
   - Реализовать метод `matches()`
   - Добавить обработку в `_bind_event_to_act()`

2. **Добавление значений переменных:**
   - Можно добавить `BindableVariableAssignment`
   - Расширить `RuntimeInfo` для хранения значений переменных

3. **Улучшение валидации:**
   - Добавить проверку по номеру строки
   - Добавить проверку по контексту вызова

## Файлы системы

- `src/runtime/bindable_events.py` - классы для связываемых событий
- `src/runtime/matcher.py` - основная логика связывания
- `src/runtime/models.py` - модели данных (RuntimeEvent, RuntimeTrace)
- `src/runtime/tracer.py` - трассировщик выполнения
- `src/runtime/executor.py` - функции выполнения с трассировкой
- `src/runtime/scenario_exporter.py` - экспорт сценариев из RuntimeTrace

## Анализ работы системы

### Будет ли это работать?

**Да, система будет работать корректно при соблюдении следующих условий:**

1. **Сценарий создан из RuntimeTrace:**
   - Сценарий должен быть создан из того же RuntimeTrace, который используется для связывания
   - Это гарантирует соответствие последовательностей условий

2. **Трасса построена из сценария:**
   - Трасса строится на основе сценария через `generate_trace_variants(cfg, [scenario])`
   - Значения условий устанавливаются из сценария при построении трассы
   - Порядок актов в трассе соответствует порядку событий в RuntimeTrace

3. **RuntimeTrace используется для связывания:**
   - При вызове `enrich_trace_with_runtime` используется тот же RuntimeTrace
   - Значения условий из RuntimeTrace перезаписывают значения из сценария (это нормально, т.к. они должны совпадать)
   - Вызовы и возвраты привязываются из RuntimeTrace

### Важные замечания

**Перезапись значений условий:**
- При построении трассы значения условий устанавливаются из сценария
- При связывании значения условий перезаписываются значениями из RuntimeTrace
- Это нормальное поведение - RuntimeTrace является источником истины
- Если значения не совпадают, это означает ошибку в сценарии или трассе

**Последовательность работы:**
1. Первичный анализ: `RuntimeTrace` → `TraceScenarioConfig` (только условия)
2. Построение трассы: `TraceScenarioConfig` → `list[TraceAct]` (условия из сценария)
3. Связывание: `list[TraceAct]` + `RuntimeTrace` → обогащенная трасса (все значения из RuntimeTrace)

**Почему это работает:**
- События в RuntimeTrace упорядочены по времени выполнения (`order`)
- Трасса упорядочена по порядку выполнения актов
- Последовательное связывание гарантирует соответствие порядков
- Строгая валидация обнаруживает несоответствия

## Потенциальные проблемы и их решение

### Проблема: Несоответствие трассы и RuntimeTrace

**Симптомы:**
- `RuntimeError`: "Required ... event not found in runtime trace"
- `ValueError`: "Event mismatch at act position ..."

**Причины:**
1. Трасса построена из сценария, который не соответствует RuntimeTrace
2. Сценарий неполный (не все условия зафиксированы)
3. Трасса содержит акты, которых не было в реальном выполнении

**Решение:**
- Убедиться, что сценарий создан из того же RuntimeTrace, который используется для связывания
- Проверить, что все условия зафиксированы в сценарии
- Убедиться, что трасса построена корректно из сценария

### Проблема: Отсутствие событий для встроенных функций

**Симптомы:**
- BEGIN/END акты встроенных функций (например, `print`, `len`) не получают runtime_info

**Причина:**
- Встроенные функции не отслеживаются трассировщиком (только пользовательские функции)

**Решение:**
- Это нормальное поведение - встроенные функции не требуют runtime_info
- Функция `_get_required_event_type` проверяет `func_name in user_functions`

### Проблема: Неправильные ast_id для условий

**Симптомы:**
- Условия не привязываются к актам
- `ValueError` при валидации условий

**Причина:**
- Неправильный маппинг `line_to_ast_id` при инструментации кода
- ast_id в ConditionEvaluation не соответствует ast_id в CFG узлах

**Решение:**
- Использовать `build_line_to_ast_id_for_conditions(ast_analyzer)` для построения маппинга
- Убедиться, что `line_to_ast_id` передается в `execute_with_trace`

## Заключение

Система связывания обеспечивает надежную привязку runtime значений к статическим трассам выполнения через последовательное связывание с строгой валидацией. Это позволяет создавать детерминированные сценарии выполнения и воспроизводить их с полной информацией о runtime значениях.

**Ключевые преимущества:**
- 100% надежность при корректных данных
- Обнаружение ошибок на раннем этапе
- Корректная обработка рекурсии и циклов
- Расширяемость для будущих улучшений
