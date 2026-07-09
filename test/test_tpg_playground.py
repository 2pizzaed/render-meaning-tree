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


def test_playground_serves_template_static_assets() -> None:
    client = playground_app.app.test_client()
    response = client.get("/static/playground.css")

    assert response.status_code == 200
    assert b".trace-container" in response.data


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

    def fake_check_graph_stepwise_reasoning(
        directory,
        pipeline,
        selected_trace,
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        captured["selected_trace"] = list(selected_trace)
        serializer, _ = registry_to_loqi(pipeline.registry)
        captured["selected_trace_names"] = [
            serializer.object_name(action) for action in selected_trace
        ]
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            result=SimpleNamespace(
                result=False,
                exceptions=[],
                trace=None,
                final_node=SimpleNamespace(
                    node_type="ExceptionNode",
                    children=None,
                    metadata=[
                        SimpleNamespace(name="id", loc_code=None, value="n-42"),
                        SimpleNamespace(name="line", loc_code=None, value="12"),
                        SimpleNamespace(
                            name="exceptionName",
                            loc_code=None,
                            value="IllegalStateException",
                        ),
                        SimpleNamespace(name="skill", loc_code="EN", value="Branching"),
                        SimpleNamespace(
                            name="explanation",
                            loc_code="EN",
                            value="Condition matched the selected branch.",
                        ),
                    ],
                ),
                variables={"answer": 42},
            )
        )

    monkeypatch.setattr(
        playground_app,
        "check_graph_stepwise_reasoning",
        fake_check_graph_stepwise_reasoning,
    )

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
    assert payload["reasoning"]["status"] == "error"
    assert payload["reasoning"]["hasException"] is True
    # finalNode несёт полную информацию; отдельных finalNodeId/Type/Line больше нет.
    final_node = payload["reasoning"]["finalNode"]
    assert final_node["nodeType"] == "ExceptionNode"
    final_node_metadata = {
        entry["name"]: entry["value"] for entry in final_node["metadata"]
    }
    assert final_node_metadata["id"] == "n-42"
    assert final_node_metadata["line"] == "12"
    assert "finalNodeId" not in payload["reasoning"]
    assert "finalNodeType" not in payload["reasoning"]
    assert "finalNodeLine" not in payload["reasoning"]
    assert payload["reasoning"]["skills"] == ["Branching"]
    assert payload["reasoning"]["explanations"] == [
        "Condition matched the selected branch."
    ]
    assert all(isinstance(action, Action) for action in captured["selected_trace"])
    assert captured["selected_trace_names"] == trace
