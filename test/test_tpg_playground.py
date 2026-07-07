from __future__ import annotations

import textwrap
from types import SimpleNamespace
from typing import Any

from src.ast_managers import prepare_code
from src.coderenderer.html import extract_buttons_from_context, prepare_html_context
from src.generator.pipeline import DomainDataGeneratorPipeline
from src.generator.utilities import registry_to_loqi
from src.model.situation import Action
from test.playground import app as playground_app
from test.playground.app import build_answer_objects


def test_build_answer_objects_exports_action_names_only() -> None:
    code = textwrap.dedent(
        """
        if x:
            y = 1
        else:
            y = 2
        """
    )
    manager = prepare_code(code, "python")
    context = prepare_html_context(manager, answer_objects={})
    buttons = extract_buttons_from_context(context)
    assert buttons

    answer_objects = build_answer_objects(manager, context, enable_trace=True)
    assert answer_objects

    pipeline = DomainDataGeneratorPipeline(manager, fork_enabled=False)
    pipeline.process()
    serializer, _ = registry_to_loqi(pipeline.registry)

    assert all(isinstance(value, str) for value in answer_objects.values())
    assert all(
        isinstance(serializer.object_by_name(str(value)), Action)
        for value in answer_objects.values()
    )


def test_reason_trace_accepts_action_name_trace(monkeypatch) -> None:
    code = textwrap.dedent(
        """
        if x:
            y = 1
        else:
            y = 2
        """
    )
    manager = prepare_code(code, "python")
    context = prepare_html_context(manager, answer_objects={})
    answer_objects = build_answer_objects(manager, context, enable_trace=True)
    assert answer_objects is not None
    trace = [str(value) for value in answer_objects.values()][:2]
    assert trace

    captured: dict[str, Any] = {}

    def fake_solve_pipeline_reasoning(directory, pipeline, **kwargs):  # type: ignore[no-untyped-def]
        serializer, _ = registry_to_loqi(pipeline.registry)
        captured["trace_names"] = [
            serializer.object_name(trace_act.action)
            for trace_act in pipeline.registry.trace_acts[1:]
        ]
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            result=SimpleNamespace(
                result=True,
                exceptions=[],
                final_node=SimpleNamespace(metadata=[]),
                variables={"answer": 42},
            )
        )

    monkeypatch.setattr(playground_app, "solve_pipeline_reasoning", fake_solve_pipeline_reasoning)

    client = playground_app.app.test_client()
    response = client.post(
        "/reason-trace",
        json={
            "code": code,
            "language": "python",
            "target_language": "",
            "trace": trace,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["ok"] is True
    assert payload["trace"] == trace
    assert payload["reasoning"]["status"] == "correct"
    assert captured["trace_names"] == trace
