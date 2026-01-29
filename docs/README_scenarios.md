# Формат файлов сценариев (*_scenarios.json)

Файлы сценариев содержат информацию о выполнении программы, включая события условий, вызовы функций и возвраты значений.

## Структура файла

Файл сценариев может быть в двух форматах:

### 1. Формат с одним сценарием

```json
{
  "scenario_name": "default",
  "events": [...],
  "conditions": [...],  // Опционально, для обратной совместимости
  "seed": 59            // Опционально
}
```

### 2. Формат с несколькими сценариями (Не рекомендуется)

> **Примечание:** Этот формат в настоящее время **не рекомендуется** для использования, хотя и поддерживается (но будет взят только первый сценарий из перечня). 
> Поскольку программный код (исходник задачи) полностью определён в файле, различные варианты выполнения одного кода не применяются (он должен выполниться единственным способом, чтобы не провоцировать нелогичности в условии задачи). 
> Формат поддерживается для будущего случая гипотетического выполнения неполностью определённого кода (подразумевая разные значения незаданных констант или результатов функций, мы сможем пускать выполнение по разным путям в коде -- это будут разные трассы для одного кода).

```json
{
  "seed": 59,            // Опционально, используется по умолчанию для всех сценариев
  "scenarios": [
    {
      "scenario_name": "scenario1",
      "events": [...],
      "conditions": [...],  // Опционально
      "seed": 60            // Опционально, переопределяет глобальный seed
    },
    {
      "scenario_name": "scenario2",
      "events": [...]
    }
  ]
}
```

## Типы событий

### Событие условия (condition)

Представляет оценку условия (if, while, for и т.д.).

```json
{
  "order": 1,
  "line_number": 3,
  "type": "condition",
  "ast_id": 55,
  "value": "true",
  "expression_text": "range(n)",
  "condition_type": "range_for"
}
```

**Поля:**
- `order` (integer, обязательное) - порядок выполнения события (начиная с 1)
- `line_number` (integer, обязательное) - номер строки в исходном коде
- `type` (string, обязательное) - всегда `"condition"`
- `ast_id` (integer | null, обязательное) - ID узла AST условия
- `value` (string, обязательное) - значение условия: `"true"` или `"false"`
- `expression_text` (string, опциональное) - текстовое представление выражения
- `condition_type` (string, опциональное) - тип условия: `"if"`, `"while"`, `"for_each"`, `"range_for"`

### Событие вызова функции (function_call)

Представляет вызов функции.

```json
{
  "order": 1,
  "line_number": 5,
  "type": "function_call",
  "ast_id": 21,
  "function_name": "factorial",
  "args": {
    "n": 5
  },
  "call_line": 5
}
```

**Поля:**
- `order` (integer, обязательное) - порядок выполнения события
- `line_number` (integer, обязательное) - номер строки в исходном коде
- `type` (string, обязательное) - всегда `"function_call"`
- `ast_id` (integer | null, обязательное) - ID узла AST вызова функции
- `function_name` (string, обязательное) - имя вызываемой функции
- `args` (object, обязательное) - аргументы функции как пары ключ-значение
- `call_line` (integer, опциональное) - номер строки, где функция была вызвана

### Событие возврата функции (function_return)

Представляет возврат значения из функции.

```json
{
  "order": 3,
  "line_number": 4,
  "type": "function_return",
  "ast_id": 18,
  "function_name": "factorial",
  "return_value": 120
}
```

**Поля:**
- `order` (integer, обязательное) - порядок выполнения события
- `line_number` (integer, обязательное) - номер строки в исходном коде
- `type` (string, обязательное) - всегда `"function_return"`
- `ast_id` (integer | null, обязательное) - ID узла AST оператора return
- `function_name` (string, обязательное) - имя функции, которая вернула значение
- `return_value` (any, обязательное) - возвращаемое значение (может быть любым JSON-значением, включая `null`)

## Устаревший формат conditions

Для обратной совместимости файлы могут содержать поле `conditions` со старым форматом:

```json
{
  "ast_id": 55,
  "condition_value": "true",
  "line_number": 3,
  "order": 1,
  "expression_text": "range(n)",
  "condition_type": "range_for"
}
```

Этот формат эквивалентен событиям типа `condition` в массиве `events`.

## JSON Schema

Полная схема валидации доступна в файле [scenarios-schema.json](./scenarios-schema.json).

Для валидации файла сценариев можно использовать инструменты, поддерживающие JSON Schema, например:

```bash
# Используя ajv-cli
ajv validate -s docs/scenarios-schema.json -d test/data/task_code/4_cycles_scenarios.json

# Используя Python с jsonschema
python -m jsonschema docs/scenarios-schema.json test/data/task_code/4_cycles_scenarios.json
```

## Примеры

### Пример 1: Простой сценарий с условиями

```json
{
  "scenario_name": "default",
  "events": [
    {
      "order": 1,
      "line_number": 3,
      "type": "condition",
      "ast_id": 55,
      "value": "true",
      "expression_text": "range(n)",
      "condition_type": "range_for"
    },
    {
      "order": 2,
      "line_number": 4,
      "type": "condition",
      "ast_id": 27,
      "value": "true",
      "expression_text": "i % 2 == 0",
      "condition_type": "if"
    }
  ]
}
```

### Пример 2: Сценарий с вызовами функций

```json
{
  "scenario_name": "default",
  "events": [
    {
      "order": 1,
      "line_number": 1,
      "type": "function_call",
      "ast_id": 21,
      "function_name": "factorial",
      "args": {
        "n": 5
      },
      "call_line": 3
    },
    {
      "order": 2,
      "line_number": 2,
      "type": "function_return",
      "ast_id": 18,
      "function_name": "factorial",
      "return_value": 120
    }
  ]
}
```

### Пример 3: Несколько сценариев

```json
{
  "seed": 59,
  "scenarios": [
    {
      "scenario_name": "scenario1",
      "events": [
        {
          "order": 1,
          "line_number": 3,
          "type": "condition",
          "ast_id": 55,
          "value": "true"
        }
      ]
    },
    {
      "scenario_name": "scenario2",
      "seed": 60,
      "events": [
        {
          "order": 1,
          "line_number": 3,
          "type": "condition",
          "ast_id": 55,
          "value": "false"
        }
      ]
    }
  ]
}
```

## Примечания

1. События в массиве `events` должны быть отсортированы по полю `order` в порядке выполнения.
2. Поле `ast_id` может быть `null`, если AST ID недоступен.
3. Поле `conditions` сохраняется для обратной совместимости, но рекомендуется использовать формат `events`.
4. Значение `return_value` может быть любым JSON-значением, включая `null`, массивы и объекты.
5. Поле `seed` используется для воспроизводимости генерации сценариев.
