"""E2E-прогон playground для сниппета: кнопки + Reason, затем Hint на каждом шаге.

Запросы идут через ``app.test_client()``: те же эндпоинты, что вызывает страница, но без
запущенного сервера. Первый прогон нажимает кнопки кода по кругу, начиная со следующей
после последней принятой, и запускает Reason; шаг принят, если Reason вернул ``correct``.
Прогон заканчивается, когда граф сообщил о завершении программы (``everything_evaluated``:
результат ``correct``, но действие в трассу не добавлено). Ошибка - ни одна кнопка не
принята до завершения или принято больше ``--limit`` шагов. Второй прогон с пустой трассы
просит Hint и сверяет каждую подсказку с действием первого прогона на том же шаге.
Падение эндпоинта (``ok: false``) или расхождение подсказки - тоже ошибка, код выхода 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from flask.testing import FlaskClient

from test.playground.app import SNIPPET_LANGUAGES_BY_SUFFIX, app

DEFAULT_SEED = 1806
DEFAULT_LIMIT = 100
_ANSWER_OBJECTS_RE = re.compile(
    r'<script type="application/json" id="answer_objects">(.*?)</script>', re.DOTALL
)
_ERROR_BOX_RE = re.compile(r'<div class="error-box">(.*?)</div>', re.DOTALL)


class PlaygroundE2EError(RuntimeError):
    """Падение эндпоинта или расхождение подсказки; сообщение готово для вывода."""


def render_actions(client: FlaskClient, form: dict[str, str]) -> list[str]:
    """Render: действия кнопок страницы и пунктов dropdown без повторов, по номеру ответа."""
    html = client.post("/", data=form).get_data(as_text=True)
    if error := _ERROR_BOX_RE.search(html):
        raise PlaygroundE2EError(f"Render failed: {error.group(1).strip()}")
    match = _ANSWER_OBJECTS_RE.search(html)
    if match is None or not match.group(1).strip():
        raise PlaygroundE2EError("Render produced no action buttons")
    # Flask сортирует ключи JSON как строки: "10" идёт перед "2".
    answers: dict[str, str | None] = json.loads(match.group(1))
    names = list(dict.fromkeys(name for key in sorted(answers, key=int) if (name := answers[key])))
    # END без значения кнопка с dropdown отправляет, только пока ни один вызов места не начат
    # (docs/ideas/function_return_dropdown.md): такой шаг всегда ошибочен, его не нажимаем.
    return [name for name in names if not any(other.startswith(f"{name},") for other in names)]


def press_buttons(
    client: FlaskClient, request: dict[str, object], actions: list[str], limit: int
) -> list[str]:
    trace: list[str] = []
    start = 0
    while True:
        for offset in range(len(actions)):
            index = (start + offset) % len(actions)
            reasoning = _post(client, "/reason-trace", request, [*trace, actions[index]])["reasoning"]
            if _program_finished(reasoning):
                return trace
            if reasoning["status"] == "correct":
                if len(trace) == limit:
                    raise PlaygroundE2EError(f"Reason accepted more than {limit} steps")
                trace.append(actions[index])
                print(f"{len(trace)}. {actions[index]} (attempts: {offset + 1})", file=sys.stderr)
                start = index + 1
                break
        else:
            raise PlaygroundE2EError(f"Reason accepted no action button at step {len(trace) + 1}")


def _program_finished(reasoning: dict) -> bool:
    final_node = reasoning["finalNode"] or {}
    return any(
        entry["name"] == "skill" and entry["value"] == "everything_evaluated"
        for entry in final_node.get("metadata", [])
    )


def check_hints(client: FlaskClient, request: dict[str, object], expected: list[str]) -> None:
    trace: list[str] = []
    while not (payload := _post(client, "/hint-trace", request, trace))["finished"]:
        action = payload["action"]
        if len(trace) >= len(expected) or action != expected[len(trace)]:
            want = expected[len(trace)] if len(trace) < len(expected) else "finished"
            raise PlaygroundE2EError(f"Hint at step {len(trace) + 1}: {action}, expected {want}")
        trace.append(action)
    if len(trace) != len(expected):
        raise PlaygroundE2EError(
            f"Hint finished at step {len(trace) + 1}, expected {expected[len(trace)]}"
        )


def _post(client: FlaskClient, url: str, request: dict[str, object], trace: list[str]) -> dict:
    payload = client.post(url, json={**request, "trace": trace}).get_json()
    if not payload or not payload.get("ok"):
        error = payload.get("error") if payload else "no JSON response"
        raise PlaygroundE2EError(f"{url} failed for trace {trace}:\n{error}")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    form = {
        "code": args.code_file.read_text(encoding="utf-8"),
        "language": args.language or SNIPPET_LANGUAGES_BY_SUFFIX[args.code_file.suffix.lower()],
        "seed": str(args.seed),
    }
    request: dict[str, object] = {**form, "no_cache": args.no_cache}
    client = app.test_client()
    try:
        actions = press_buttons(client, request, render_actions(client, form), args.limit)
        if not actions:
            raise PlaygroundE2EError("Reason accepted no action button")
        print("Hint check...", file=sys.stderr)
        check_hints(client, request, actions)
    except PlaygroundE2EError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(actions, indent=2, ensure_ascii=False))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Press playground action buttons with Reason, then check Hint on every step."
    )
    parser.add_argument("code_file", type=Path, help="Snippet file, as loaded into the playground.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Problem generation seed.")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Maximum number of trace steps; Reason accepting more is an error.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Recheck the whole trace on every Reason and Hint instead of the accepted prefix cache.",
    )
    parser.add_argument(
        "--language",
        choices=sorted(set(SNIPPET_LANGUAGES_BY_SUFFIX.values())),
        help="Snippet language (default: by file extension).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
