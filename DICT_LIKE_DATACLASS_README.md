# DictLikeDataclass - Реализация TODO

## Описание

Реализованы все TODO для класса `DictLikeDataclass` в файле `src/common_utils.py`. Теперь возможно создавать дерево связанных объектов data-классов из JSON-данных.

## Реализованные возможности

### 1. Метод `make(cls, data: dict)`
Класс-метод для создания экземпляра dataclass из словаря JSON-данных.

**Функциональность:**
- ✅ Проверка наличия неизвестных ключей в данных
- ✅ Проверка обязательных полей (mandatory fields)
- ✅ Поддержка опциональных полей (Optional fields)
- ✅ Рекурсивное создание вложенных dataclass объектов
- ✅ Поддержка списков (List[T])
- ✅ Поддержка словарей (Dict[K, V])
- ✅ Автоматическое преобразование Enum через `SelfValidatedEnum.lookup`
- ✅ Поддержка примитивных типов (int, float, str, bool)
- ✅ Поддержка Union типов

### 2. Метод `_get_type_hints(cls)`
Класс-метод для получения информации о типах полей и их опциональности.

**Возвращает:**
- Словарь `dict[str, tuple[type, bool]]`, где:
  - ключ - имя поля
  - значение - кортеж (тип поля, флаг optional)

**Определение optional полей:**
- Поле имеет значение по умолчанию (`field.default is not MISSING`)
- Поле имеет фабрику по умолчанию (`field.default_factory is not MISSING`)
- Поле имеет тип `Optional[T]` (т.е. `Union[T, None]`)

### 3. Метод `_process_value(cls, value, field_type, is_optional)`
Внутренний класс-метод для обработки значений согласно их типам.

**Поддерживаемые типы:**
- `None` для опциональных полей
- `Union` и `Optional[T]`
- `List[T]` с рекурсивной обработкой элементов
- `Dict[K, V]` с рекурсивной обработкой ключей и значений
- `SelfValidatedEnum` с автоматическим lookup
- Вложенные dataclass с рекурсивным созданием
- Примитивные типы (int, float, str, bool)
- `Any` тип

## Примеры использования

### Пример 1: Простой dataclass

```python
from dataclasses import dataclass
from typing import Optional
from src.common_utils import DictLikeDataclass

@dataclass
class Person(DictLikeDataclass):
    name: str
    age: int
    email: Optional[str] = None

# Создание из JSON
data = {"name": "John", "age": 30, "email": "john@example.com"}
person = Person.make(data)
print(person.name)  # John
print(person.age)   # 30
```

### Пример 2: Вложенные dataclass

```python
from dataclasses import dataclass, field
from typing import List
from src.common_utils import DictLikeDataclass

@dataclass
class Address(DictLikeDataclass):
    street: str
    city: str

@dataclass
class Company(DictLikeDataclass):
    name: str
    address: Address
    employees: List[Person] = field(default_factory=list)

data = {
    "name": "Tech Corp",
    "address": {
        "street": "Main St",
        "city": "New York"
    },
    "employees": [
        {"name": "Alice", "age": 25},
        {"name": "Bob", "age": 30}
    ]
}

company = Company.make(data)
print(company.address.city)  # New York
print(len(company.employees))  # 2
```

### Пример 3: Использование с Enum

```python
from src.common_utils import SelfValidatedEnum

class Status(SelfValidatedEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"

@dataclass
class User(DictLikeDataclass):
    name: str
    status: Status

data = {"name": "Alice", "status": "active"}
user = User.make(data)
print(user.status == Status.ACTIVE)  # True
```

### Пример 4: Парсинг AST из JSON

```python
import json

@dataclass
class ASTNode(DictLikeDataclass):
    type: str
    id: Optional[int] = None
    name: Optional[str] = None
    body: Optional[List[Dict[str, Any]]] = None

with open("ast.json") as f:
    ast_data = json.load(f)

root = ASTNode.make(ast_data)
print(root.type)  # program_entry_point
```

## Обработка ошибок

Класс выбрасывает `ValueError` в следующих случаях:

1. **Неизвестные ключи**: если в данных есть поля, не определенные в dataclass
2. **Отсутствие обязательных полей**: если обязательное поле отсутствует в данных
3. **Неверный тип данных**: если значение не может быть преобразовано к нужному типу
4. **Неверное значение Enum**: если значение не соответствует ни одному значению Enum

## Тестирование

Реализованы комплексные тесты в файле `test/test_dict_like_dataclass.py`:

```bash
python -m pytest test/test_dict_like_dataclass.py -v
```

**Результаты тестов:**
- ✅ 10/10 тестов проходят успешно
- ✅ Тестируются все основные сценарии использования
- ✅ Тестируется обработка ошибок
- ✅ Тестируется парсинг реальных AST данных

## Демонстрация

Запустите демонстрационный скрипт для просмотра возможностей:

```bash
python demo_dict_like_dataclass.py
```

## Технические детали

### Архитектура решения

1. **make()** - точка входа для создания объекта
2. **_get_type_hints()** - анализ структуры класса
3. **_process_value()** - рекурсивная обработка значений

### Особенности реализации

- Все методы являются classmethods для удобства использования
- Поддержка рекурсивного создания вложенных структур
- Автоматическое определение обязательных/опциональных полей
- Поддержка forward references через тип `Any`
- Полная совместимость с существующим кодом проекта

## Изменения в коде

**Измененные файлы:**
- `src/common_utils.py` - реализованы все TODO

**Новые файлы:**
- `test/test_dict_like_dataclass.py` - комплексные тесты
- `demo_dict_like_dataclass.py` - демонстрационный скрипт
- `DICT_LIKE_DATACLASS_README.md` - данная документация

## Заключение

Все TODO успешно реализованы. Класс `DictLikeDataclass` теперь поддерживает полноценное создание дерева связанных объектов data-классов из JSON-данных с автоматической валидацией, преобразованием типов и обработкой ошибок.
