from pathlib import Path

import pytest
from flask import Flask, Response, jsonify, request

from test.playground.app import app as playground_app
from test.tools.playground_e2e import (
    DEFAULT_LIMIT,
    DEFAULT_SEED,
    PlaygroundE2EError,
    check_hints,
    press_buttons,
    render_actions,
)


@pytest.mark.e2e
@pytest.mark.parametrize(
    "code_file",
    [
        pytest.param(path, id=path.name)
        for path in sorted(
            (Path(__file__).parent / "data/task_code/recursion").glob("*.py")
        )
    ],
)
def test_recursion_playground_e2e(code_file: Path) -> None:
    """Проверить Reason, Hint и завершение программы для каждого примера рекурсии."""
    form = {
        "code": code_file.read_text(encoding="utf-8"),
        "language": "python",
        "target_language": "",
        "seed": str(DEFAULT_SEED),
    }
    request_payload: dict[str, object] = {**form, "no_cache": False}
    with playground_app.test_client() as client:
        actions = press_buttons(
            client, request_payload, render_actions(client, form), DEFAULT_LIMIT
        )
        assert actions, "Reason accepted no action button"
        check_hints(client, request_payload, actions)


@pytest.mark.parametrize(
    "hint_status,hint_ok,step_offset",
    [
        (409, False, 0),
        (200, False, 0),
        (500, False, 0),
        (409, True, 0),
        (409, False, 1),
    ],
)
def test_rejected_buttons_check_hint_with_a_bounded_budget(
    hint_status: int,
    hint_ok: bool,
    step_offset: int,
) -> None:
    app = Flask(__name__)
    hint_traces: list[list[str]] = []

    @app.post("/reason-trace")
    def reason() -> Response:
        trace = request.get_json()["trace"]
        finished = len(trace) == 6
        correct = finished or trace[-1] == "next"
        return jsonify(
            ok=True,
            failedStepIndex=None if correct else len(trace) - 1,
            reasoning={
                "status": "correct" if correct else "error",
                "hasException": False,
                "explanations": [] if correct else ["This action is premature."],
                "finalNode": {
                    "metadata": [{"name": "skill", "value": "everything_evaluated"}]
                }
                if finished
                else None,
            },
        )

    @app.post("/hint-trace")
    def hint() -> tuple[Response, int]:
        trace = request.get_json()["trace"]
        hint_traces.append(trace)
        return jsonify(
            ok=hint_ok,
            error=f"Trace is incorrect at step {len(trace) + step_offset}; fix it before requesting a hint.",
        ), hint_status

    if hint_status == 409 and not hint_ok and step_offset == 0:
        assert (
            press_buttons(app.test_client(), {}, ["bad-a", "bad-b", "next"], 10)
            == ["next"] * 5
        )
        assert hint_traces == [["next"] * step + ["bad-a"] for step in range(3)]
    else:
        with pytest.raises(PlaygroundE2EError, match="Hint"):
            press_buttons(app.test_client(), {}, ["bad-a", "bad-b", "next"], 10)


@pytest.mark.parametrize(
    "status,failed_index,explanations",
    [
        ("unknown", 0, ["Unknown action."]),
        ("error", 1, ["Wrong step index."]),
        ("error", 0, []),
        ("error", 0, ["  "]),
    ],
)
def test_invalid_reason_rejection_fails(
    status: str,
    failed_index: int,
    explanations: list[str],
) -> None:
    app = Flask(__name__)

    @app.post("/reason-trace")
    def reason() -> Response:
        return jsonify(
            ok=True,
            failedStepIndex=failed_index,
            reasoning={
                "status": status,
                "finalNode": None,
                "explanations": explanations,
            },
        )

    with pytest.raises(PlaygroundE2EError, match="rejection"):
        press_buttons(app.test_client(), {}, ["bad"], 10)
