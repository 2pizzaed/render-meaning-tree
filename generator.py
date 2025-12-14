import argparse
import json
import sys
from pathlib import Path

from src.cfg.condition_exporter import load_scenarios_from_file
from src.qgen_utils import build_questions

debug = True

def detect_lang(path: str):
    match Path(path).suffix:
        case ".py":
            return "python"
        case ".c", ".cpp", ".hpp", ".h":
            return "c++"
        case ".java":
            return "java"


def get_scenario_name_from_question(question: dict) -> str:
    """Извлекает имя сценария из вопроса для формирования имени файла."""
    # Имя сценария может быть в questionName или в metadataList
    qname = question.get("commonQuestion", {}).get("questionData", {}).get("questionName", "")
    # Если имя содержит подчёркивание, возможно это base_name_scenario_name
    if "_" in qname:
        parts = qname.rsplit("_", 1)
        if len(parts) == 2:
            return parts[1]
    return "default"


parser = argparse.ArgumentParser(
    description="Генератор вопросов из исходного кода"
)
parser.add_argument(
    "path",
    help="Путь к входному файлу или '-' для чтения из stdin"
)
parser.add_argument(
    "lang",
    nargs="?",
    help="Язык программирования (python, c++, java). Автоматически определяется по расширению файла, если не указан"
)
parser.add_argument(
    "--output-dir", "-o",
    help="Директория для выходных JSON файлов. Если не указана, вывод идёт на stdout"
)
parser.add_argument(
    "--output-name",
    help="Базовое имя для выходных файлов (по умолчанию берётся из имени входного файла)"
)

args = parser.parse_args()

path = args.path
lang = args.lang or detect_lang(path)

if not lang:
    print("Ошибка: Не обнаружен язык программирования, укажите его явно", file=sys.stderr)
    sys.exit(1)

try:
    if path == "-":
        content = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as f:
            content = f.read()
except FileNotFoundError:
    print(f"Ошибка: Файл '{path}' не найден.", file=sys.stderr)
    sys.exit(1)
except OSError as e:
    # Обработка других ошибок ввода-вывода
    print(f"Ошибка чтения '{path}': {e}", file=sys.stderr)
    sys.exit(1)

# Пытаемся загрузить планы сценариев, если файл существует
scenario_plans = None
scenario_names_list = None
if path != "-":
    path_obj = Path(path)
    scenarios_file = path_obj.parent / f"{path_obj.stem}_scenarios.json"
    if scenarios_file.exists():
        scenario_plans = load_scenarios_from_file(scenarios_file)
        # Сохраняем имена сценариев для использования при формировании имён файлов
        scenario_names_list = [plan.get("scenario_name", "default") for plan in scenario_plans]

questions = build_questions(
    lang,
    content,
    "debug_" + Path(path).name if debug and path != "-" else None,
    scenario_plans=scenario_plans,
)

if not questions:
    sys.exit(1)

# Определяем базовое имя файла
if args.output_name:
    base_name = args.output_name
elif path != "-":
    base_name = Path(path).stem
else:
    base_name = "output"

# Если указана выходная директория, записываем в файлы
if args.output_dir:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for i, question in enumerate(questions):
        # Определяем имя сценария
        if scenario_names_list and i < len(scenario_names_list):
            scenario_name = scenario_names_list[i]
        else:
            # Fallback: пытаемся извлечь из имени вопроса
            scenario_name = get_scenario_name_from_question(question)
        
        # Формируем имя файла
        if scenario_name == "default" and len(questions) == 1:
            # Если только один вопрос с default, используем просто base_name
            filename = output_dir / f"{base_name}.json"
        else:
            # Иначе добавляем имя сценария
            filename = output_dir / f"{base_name}_{scenario_name}.json"
        
        # Записываем вопрос в файл
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(question, f, indent=2, ensure_ascii=False)
else:
    # Выводим в stdout только первый вопрос (для обратной совместимости)
    first_question = questions[0]
    print(json.dumps(first_question, ensure_ascii=False))
