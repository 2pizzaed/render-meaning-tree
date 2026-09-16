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
    css_response = client.get("/static/playground.css")
    js_response = client.get("/static/playground.js")

    assert css_response.status_code == 200
    assert b".trace-container" in css_response.data
    assert js_response.status_code == 200
    assert b"findSourceMapNodePath" in js_response.data
    assert b"sourceMapEditor.setSelection({path})" in js_response.data
    assert b"initializeNodeIdSearch" in js_response.data


def test_playground_renders_node_id_search_when_source_map_is_available() -> None:
    with playground_app.app.app_context():
        rendered = playground_app.app.jinja_env.get_template(
            "playground.html"
        ).render(
            static_used=True,
            lines=[],
            error=None,
            nodes_json="{}",
            source_map={"type": "source_map", "origin": {}},
            enable_trace=False,
            answer_objects=None,
        )

    assert 'id="node-id-search-input"' in rendered
    assert 'id="node-id-search-form"' in rendered
    assert 'class="ri-search-line"' in rendered


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
            step_index=len(selected_trace) - 1,
            loqi_text="obj reason_input : ActionSpec {}",
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
    assert payload["failedStepIndex"] == len(trace) - 1
    assert payload["loqi"] == "obj reason_input : ActionSpec {}"
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


def _hint_request_setup(monkeypatch, *, finished: bool) -> tuple[str, Any]:
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
    names = [str(value) for value in answer_objects.values()]
    trace, hint_name = names[:1], names[1]

    def fake_check_graph_stepwise_reasoning(directory, pipeline, selected_trace, **kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            step_index=len(selected_trace) - 1,
            loqi_text="obj check_input : ActionSpec {}",
            result=SimpleNamespace(result=True, exceptions=[]),
        )

    def fake_find_graph_next_correct_action(directory, pipeline, **kwargs):  # type: ignore[no-untyped-def]
        serializer, _ = registry_to_loqi(pipeline.registry)
        action = None if finished else serializer.object_by_name(hint_name)
        return SimpleNamespace(
            action=action,
            finished=finished,
            output=SimpleNamespace(loqi_text="obj hint_input : ActionSpec {}"),
        )

    monkeypatch.setattr(playground_app, "check_graph_stepwise_reasoning", fake_check_graph_stepwise_reasoning)
    monkeypatch.setattr(playground_app, "find_graph_next_correct_action", fake_find_graph_next_correct_action)

    response = playground_app.app.test_client().post(
        "/hint-trace",
        json={"code": code, "language": "python", "target_language": "", "trace": trace},
    )
    assert response.status_code == 200
    return hint_name, response.get_json()


def test_hint_trace_returns_next_action_name(monkeypatch) -> None:
    hint_name, payload = _hint_request_setup(monkeypatch, finished=False)

    assert payload["ok"] is True
    assert payload["finished"] is False
    assert payload["action"] == hint_name
    # LOQI последнего запуска reasoner: findCorrect идёт после пошаговой проверки.
    assert payload["loqi"] == "obj hint_input : ActionSpec {}"


def test_hint_trace_reports_finished_program(monkeypatch) -> None:
    _, payload = _hint_request_setup(monkeypatch, finished=True)

    assert payload["ok"] is True
    assert payload["finished"] is True
    assert payload["action"] is None


def test_trace_template_renders_loqi_viewer_only_outside_static_page() -> None:
    template = playground_app.app.jinja_env.get_template("playground_trace.html")
    with playground_app.app.app_context():
        interactive = template.render(static_used=False)
        static = template.render(static_used=True)

    assert 'id="loqi-button"' in interactive
    assert 'id="loqi-modal"' in interactive
    assert 'id="loqi-search-input"' in interactive
    assert 'id="loqi-button"' not in static
    assert 'id="loqi-modal"' not in static
