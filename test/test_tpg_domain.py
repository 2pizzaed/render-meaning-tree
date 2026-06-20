from __future__ import annotations

import io
import logging
import subprocess
from pathlib import Path

from src.tpg_domain import (
    ExpressionQueryResult,
    ReasoningException,
    ReasoningResult,
    _run_reasoner_cli,
    parse_expression_query_jsonl,
    parse_reasoning_jsonl,
    query_expression,
    solve_reasoning,
)


def test_parse_reasoning_jsonl_builds_structured_result() -> None:
    raw_jsonl = "\n".join(
        [
            '{"type":"reasoner-output","level":"debug","value":"checking node"}',
            '{"type":"result","name":"branchResult","value":"Correct"}',
            '{"type":"variables","value":{"x":"1"}}',
            '{"type":"exceptions","found":true,"value":[{"id":"node-1","result":"Error","exceptionName":"IllegalStateException"}]}',
            '{"type":"trace","value":"Result: Correct\\nVariables:\\n  x = 1"}',
            '{"type":"artifact","name":"specificDomain","format":"loqi","value":"obj demo : Demo {}"}',
        ]
    )

    result = parse_reasoning_jsonl(raw_jsonl)

    assert isinstance(result, ReasoningResult)
    assert result.result is True
    assert result.reasoner_output == ["checking node"]
    assert result.variables == {"x": "1"}
    assert result.exceptions == [
        ReasoningException(
            id="node-1", result=False, exception_name="IllegalStateException"
        )
    ]
    assert result.trace == "Result: Correct\nVariables:\n  x = 1"
    assert result.trace_format == "text"
    assert result.artifacts["specificDomain"] == "obj demo : Demo {}"


def test_parse_reasoning_jsonl_can_print_reasoner_output_to_stream() -> None:
    stream = io.StringIO()

    result = parse_reasoning_jsonl(
        '{"type":"reasoner-output","level":"debug","value":"step one"}',
        reasoner_output_stream=stream,
    )

    assert result.reasoner_output == ["step one"]
    assert stream.getvalue() == "step one\n"


def test_parse_expression_query_jsonl_builds_structured_result() -> None:
    raw_jsonl = "\n".join(
        [
            '{"type":"reasoner-output","value":"query started"}',
            '{"type":"expression-query-result","objects":["obj_a","obj_b"]}',
            '{"type":"expression-trace","value":"Expression trace: ..."}',
            '{"type":"metric","name":"queryTime","seconds":0.1}',
        ]
    )

    result = parse_expression_query_jsonl(raw_jsonl)

    assert result == ExpressionQueryResult(
        objects=["obj_a", "obj_b"],
        trace="Expression trace: ...",
        reasoner_output=["query started"],
        metrics={"queryTime": {"type": "metric", "name": "queryTime", "seconds": 0.1}},
    )


def test_solve_reasoning_requests_jsonl_and_text_trace_by_default(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_reasoner_cli(*args: str) -> str:
        calls.append(args)
        return '{"type":"result","value":true}'

    monkeypatch.setattr("src.tpg_domain._run_reasoner_cli", fake_run_reasoner_cli)

    result = solve_reasoning("domain", "generated.loqi", tree="findCorrect")

    assert isinstance(result, ReasoningResult)
    assert result.result is True
    assert "--format" in calls[0]
    assert calls[0][calls[0].index("--format") + 1] == "jsonl"
    assert "--json-trace" not in calls[0]


def test_solve_reasoning_can_request_json_trace(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_reasoner_cli(*args: str) -> str:
        calls.append(args)
        return "\n".join(
            [
                '{"type":"result","value":true}',
                '{"type":"trace","value":{"branchResult":"Correct","elements":[]}}',
            ]
        )

    monkeypatch.setattr("src.tpg_domain._run_reasoner_cli", fake_run_reasoner_cli)

    result = solve_reasoning("domain", "generated.loqi", json_trace=True)

    assert isinstance(result, ReasoningResult)
    assert result.trace == {"branchResult": "Correct", "elements": []}
    assert result.trace_format == "json"
    assert "--json-trace" in calls[0]


def test_query_expression_requests_jsonl_and_supports_optional_model(
    monkeypatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_reasoner_cli(*args: str) -> str:
        calls.append(args)
        return '{"type":"expression-query-result","objects":["obj_1"]}'

    monkeypatch.setattr("src.tpg_domain._run_reasoner_cli", fake_run_reasoner_cli)

    result = query_expression(
        "generated.loqi",
        "$x->prop == 1",
        model_dir="domain",
        tag="demo",
        debug_enabled=True,
        trace=True,
        verbose=True,
        limit=3,
        time_measure=True,
    )

    assert result == ExpressionQueryResult(objects=["obj_1"])
    assert calls[0][:4] == (
        "expression-query",
        "domain",
        "generated.loqi",
        "$x->prop == 1",
    )
    assert "--tag" in calls[0]
    assert "--debug" in calls[0]
    assert "--trace" in calls[0]
    assert "--verbose" in calls[0]
    assert "--limit" in calls[0]
    assert "--time-measure" in calls[0]
    assert calls[0][calls[0].index("--format") + 1] == "jsonl"


def test_reasoning_result_str_is_human_readable() -> None:
    result = ReasoningResult(
        result=False,
        trace={"branchResult": "Error", "elements": []},
        variables={"z": "last", "a": "first"},
        exceptions=[
            ReasoningException(
                id="node-1", result=False, exception_name="IllegalStateException"
            )
        ],
        metrics={
            "solveTime": {
                "type": "metric",
                "name": "solveTime",
                "seconds": 1.5,
                "milliseconds": 1500.0,
            }
        },
        artifact_paths={"specificDomain": Path("out.loqi")},
    )

    rendered = str(result)

    assert "Result: False" in rendered
    assert (
        "Exceptions:\n  - id=node-1; result=False; exceptionName=IllegalStateException"
        in rendered
    )
    assert (
        'Trace:\n  {\n    "branchResult": "Error",\n    "elements": []\n  }' in rendered
    )
    assert "Variables:\n  a = first\n  z = last" in rendered
    assert (
        'Metrics:\n  solveTime: {\n      "seconds": 1.5,\n      "milliseconds": 1500.0\n    }'
        in rendered
    )
    assert "Artifact paths:\n  specificDomain: out.loqi" in rendered


def test_run_reasoner_cli_logs_jsonl_errors_as_readable_exception(
    monkeypatch, caplog
) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=args[0],
            stderr=(
                '{"type":"error",'
                '"exceptionName":"java.lang.IllegalArgumentException",'
                '"message":"Failed requirement.",'
                '"stackTrace":"java.lang.IllegalArgumentException: Failed requirement.\\n\\tat demo.Main"}'
            ),
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    with caplog.at_level(logging.ERROR, logger="src.tpg_domain"):
        result = _run_reasoner_cli(
            "reason", "domain", "generated.loqi", "--format", "jsonl"
        )

    assert result is None
    assert (
        "its_Reasoner CLI error java.lang.IllegalArgumentException: Failed requirement."
        in caplog.text
    )
    assert (
        "java.lang.IllegalArgumentException: Failed requirement.\n\tat demo.Main"
        in caplog.text
    )
    assert '\\"stackTrace\\"' not in caplog.text


def test_run_reasoner_cli_logs_variables_event_on_failure(
    monkeypatch, caplog
) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=args[0],
            stderr="\n".join(
                [
                    '{"type":"variables","value":{"x":"1","state":"failed"}}',
                    '{"type":"error","message":"boom"}',
                ]
            ),
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    with caplog.at_level(logging.ERROR, logger="src.tpg_domain"):
        result = _run_reasoner_cli(
            "reason", "domain", "generated.loqi", "--format", "jsonl"
        )

    assert result is None
    assert 'Variables:\n{\n  "x": "1",\n  "state": "failed"\n}' in caplog.text
