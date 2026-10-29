# render-meaning-tree

Генератор учебных задач на порядок выполнения кода для тренажёра CompPrehension. По фрагменту кода на Python, Java или C++ он строит ситуацию, подбирает значения условий, получает эталонную трассу с помощью рассуждателя по графу мыслительного процесса (TPG) и отбирает задачи для студента.

## Основные команды

### `uv run generate-problems` — генерация задач

Генерирует задачи по фрагменту кода и печатает отобранные: значения условий, число шагов, оценку Q, скиллы и концепты. Логи pipeline с причинами отказов пишутся в stderr.

```bash
uv run generate-problems snippet.py                         # язык по умолчанию: python
uv run generate-problems Snippet.java --language java
uv run generate-problems snippet.py --target-language java  # задачи на переводе фрагмента в Java
uv run generate-problems snippet.py --output out/           # сохранить вопросы CompPrehension в JSON
uv run generate-problems snippets/ --output out/            # рекурсивно обработать каталог Python-сниппетов
uv run generate-problems snippets/ --language java --output out/  # только Java-сниппеты
```

При входном каталоге каждый файл — отдельный сниппет, для которого отбирается до `--top-k` задач. Язык задаётся общим `--language` (по умолчанию `python`); файлы других языков и неизвестных расширений пропускаются. Задачи всех сниппетов записываются прямо в `out/`, имя файла начинается с относительного пути сниппета без расширения: задачи `snippets/loops/example.py` — в `out/loops__example__<questionName>.json`. Для одного входного файла JSON по-прежнему записываются прямо в `out/`.

В пакетном режиме команда показывает прогресс и итоговые количества сниппетов, задач и сохранённых вопросов. Ошибка одного файла не мешает обработать остальные; код завершения — `1` при ошибках файлов или отсутствии подходящих сниппетов. Отклонённый генератором сниппет может дать ноль задач. Повторный запуск перезаписывает вопросы с тем же именем; старые файлы автоматически не удаляются.

Другие опции: `--seed`, `--top-k`, `--selection score|random`, `--origin` и `--origin-license` (источник фрагмента для метаданных вопроса).

Значения условий можно задать вручную маркером в конце строки заголовка: `while i < n:  # <! TTF >`. Для условий внутри рекурсивных функций разметка обязательна. Подробнее — в [docs/generator_pipeline.md](docs/generator_pipeline.md).

### `uv run playground` — интерактивная проверка

Веб-интерфейс (Flask, по умолчанию <http://127.0.0.1:5000>) для ручной проверки домена и генератора:

- загрузить фрагмент из `test/data` или вставить свой, выбрать язык и, при необходимости, язык перевода;
- с seed — открыть сгенерированную задачу, без seed — ситуацию со значениями по умолчанию;
- решать задачу кнопками действий: Reason проверяет шаг, Hint подсказывает следующий;
- посмотреть эталонную трассу и экспортировать задачу как вопрос CompPrehension.

Опции: `--host`, `--port`, `--snippets-dir`, `--no-debug`.

## Установка

Нужны: [uv](https://docs.astral.sh/uv/), JDK и Maven, Git. На Windows скрипты запускаются в Git Bash. Для SVG-схем трассы в playground нужен [Graphviz](https://graphviz.org/) (`dot` в `PATH`).

```bash
git clone --recurse-submodules <адрес этого репозитория> && cd render-meaning-tree
uv sync
cp .env.example .env    # затем прописать пути, см. ниже
```

Подмодуль `meaning_tree/` — это Meaning Tree, транслятор кода в универсальное AST. Рассуждатель и модель домена — отдельные проекты `its_DomainModel` и `its_Reasoner`, их нужно склонировать рядом.

### Сборка Java-библиотек: `build_libs.sh`

Собирает библиотеки через `mvn clean install` в локальный репозиторий Maven (`~/.m2`), а затем пересобирает RPC-сервер (`rpc_server.sh build`).

```bash
./build_libs.sh          # всё: its_DomainModel, its_Reasoner, meaning_tree
./build_libs.sh tpg      # только its_DomainModel и its_Reasoner
./build_libs.sh mt       # только meaning_tree
```

Пути задаются в `.env`:

| Переменная | Значение |
| --- | --- |
| `ITS_DOMAINMODEL_PATH` | каталог `its_DomainModel` |
| `ITS_REASONER_PATH` | каталог `its_Reasoner` |
| `MEANING_TREE_PATH` | каталог Meaning Tree, по умолчанию `./meaning_tree` |

### RPC-сервер: `rpc_server.sh`

Python-часть вызывает Java-инструменты (Meaning Tree, its_DomainModel, its_Reasoner) одним из двух способов:

- `cli` — запуск JAR из `~/.m2` отдельным процессом на каждый вызов. Работает без сервера, но каждый вызов заново поднимает JVM, а генерация одного фрагмента вызывает рассуждатель десятки и сотни раз;
- `rpc` — вызовы по JSON-RPC к постоянно запущенному `compph-toolchain-server`. Это намного быстрее, поэтому рекомендуется. Тот же сервер отдаёт MCP-инструменты для агентов (`/mcp`, см. `.mcp.json`).

```bash
./rpc_server.sh build            # собрать сервер (mvn package)
./rpc_server.sh start [--build]  # запустить в фоне, лог — .rpc_server.log
./rpc_server.sh status
./rpc_server.sh stop
```

Настройки в `.env`:

| Переменная | Значение |
| --- | --- |
| `TOOLCHAIN_SERVER_PATH` | каталог проекта `compph-toolchain-server` (обязательно) |
| `JSON_RPC_TOOLCHAIN_PORT`, `JSON_RPC_TOOLCHAIN_HOST` | порт и адрес, на которых запускается сервер |
| `JSON_RPC_TOOLCHAIN_SERVER` | адрес, по которому к серверу обращается Python, например `http://localhost:9001`; порт должен совпадать с `JSON_RPC_TOOLCHAIN_PORT` |
| `JSON_RPC_TOOLCHAIN_ACCESS_SECRET` | общий секрет; пусто, если сервер без секрета |
| `TOOLCHAIN_BACKEND` | `rpc`, `cli` или `auto` (RPC, если сервер доступен, иначе CLI); переопределения для отдельных инструментов — `MEANING_TREE_BACKEND`, `TPG_BACKEND` |
| `TOOLCHAIN_LOCAL_FILES` | `true` — передавать серверу пути к файлам вместо содержимого; только для локального сервера с `LOCAL_FILES_DISCOVERY=true` |

После изменения Java-библиотек сервер нужно пересобрать и перезапустить: `./build_libs.sh …`, затем `./rpc_server.sh stop && ./rpc_server.sh start`.

## Для разработчиков

Проверки:

```bash
uv run pytest            # все тесты; make test — параллельно (xdist) и затем serial-тесты
uv run ruff check .
uv run pyright
```

Инструменты отладки:

| Команда | Назначение |
| --- | --- |
| `uv run playground-e2e FILE [--seed N] [--target-language LANG]` | e2e-прогон playground без сервера: кнопки + Reason до конца программы, затем сверка Hint на каждом шаге |
| `uv run annotate-trace FILE` | выполнить Python-фрагмент и вывести его с маркерами `<! … >` по реальной трассе |
| `uv run find-correct-trace-actions` | последовательность действий findCorrect для фрагмента |
| `uv run render-code-html (FILE \| --stdin --lang LANG) [-o OUT] [--no-buttons] [--no-style] [--no-icon-styles]` | статический HTML-сниппет кода (`templates/code_component.html`) в stdout или файл; язык файла — по расширению; со ссылкой на Remix Icon из CDN для иконок кнопок (кроме `--no-buttons` и `--no-icon-styles`) |
| `uv run render-construct-automaton` | автомат переходов конструкции по правилам из `src/resources/constructs.yml` |
| `uv run tree-loqi-to-xml` | перевести дерево TPG/LOQI в XML для диагностики синтаксиса |
| `uv run validate-dsm` | проверить модель домена (DomainSolvingModel) |

Структура:

- `src/` — генератор (`src/generator/`), модель ситуации, сериализация в LOQI, клиенты Meaning Tree и TPG;
- `domain/` — домен и графы рассуждений (`main.tpg`, `findCorrect.tpg`, `domain.loqi`);
- `test/playground/` — playground, `test/tools/` — инструменты отладки, `test/data/` — фрагменты кода;
- `docs/` — документация: pipeline генератора ([generator_pipeline.md](docs/generator_pipeline.md)), домен ([domain.md](docs/domain.md)), графы проверки и поиска правильного шага ([check_graph_idea.md](docs/check_graph_idea.md), [findCorrect_graph_idea.md](docs/findCorrect_graph_idea.md)).
