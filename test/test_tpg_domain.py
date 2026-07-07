from __future__ import annotations

import io
import logging
import subprocess
from pathlib import Path

from src.toolchain_rpc import RpcError
from src.tpg_domain import (
    DiscoverTreeResult,
    ExpressionQueryResult,
    ReasoningException,
    ReasoningResult,
    TreeNode,
    TreeNodeChildren,
    TreeNodeDescriptor,
    TreeNodeMetadataEntry,
    parse_discover_tree_jsonl,
    parse_expression_query_jsonl,
    parse_reasoning_jsonl,
)
from src.tpg_domain.cli import (
    _run_reasoner_cli,
    discover_tree,
    query_expression,
    solve_reasoning,
)
from src.tpg_domain.rpc import discover_tree as discover_tree_rpc
from src.tpg_domain.rpc import query_expression as query_expression_rpc
from src.tpg_domain.rpc import solve_reasoning as solve_reasoning_rpc


def test_parse_reasoning_jsonl_builds_structured_result() -> None:
    raw_jsonl = "\n".join(
        [
            '{"type":"reasoner-output","level":"debug","value":"checking node"}',
            '{"type":"result","name":"branchResult","value":"Correct"}',
            '{"type":"final-node","nodeType":"BranchResultNode","metadata":[{"name":"id","locCode":null,"value":"n1"},{"name":"label","locCode":"ru","value":"Итог"}]}',
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
    assert result.final_node == TreeNode(
        node_type="BranchResultNode",
        metadata=[
            TreeNodeMetadataEntry(name="id", loc_code=None, value="n1"),
            TreeNodeMetadataEntry(name="label", loc_code="ru", value="Итог"),
        ],
    )


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
            '{"type":"expression-query-result","objects":["obj_a","obj_b"],'
            '"objectsLoqi":[{"name":"obj_a","loqi":"obj obj_a : Demo {}"},'
            '{"name":"obj_b","loqi":"obj obj_b : Demo {}"}]}',
            '{"type":"expression-trace","value":"Expression trace: ..."}',
            '{"type":"metric","name":"queryTime","seconds":0.1}',
        ]
    )

    result = parse_expression_query_jsonl(raw_jsonl)

    assert result == ExpressionQueryResult(
        objects=["obj_a", "obj_b"],
        objects_loqi={
            "obj_a": "obj obj_a : Demo {}",
            "obj_b": "obj obj_b : Demo {}",
        },
        trace="Expression trace: ...",
        reasoner_output=["query started"],
        metrics={"queryTime": {"type": "metric", "name": "queryTime", "seconds": 0.1}},
    )


def test_solve_reasoning_requests_jsonl_and_text_trace_by_default(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_reasoner_cli(*args: str) -> str:
        calls.append(args)
        return '{"type":"result","value":true}'

    monkeypatch.setattr("src.tpg_domain.cli._run_reasoner_cli", fake_run_reasoner_cli)

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

    monkeypatch.setattr("src.tpg_domain.cli._run_reasoner_cli", fake_run_reasoner_cli)

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

    monkeypatch.setattr("src.tpg_domain.cli._run_reasoner_cli", fake_run_reasoner_cli)

    result = query_expression(
        "generated.loqi",
        "$x->prop == 1",
        model_dir="domain",
        tag="demo",
        debug_enabled=True,
        trace=True,
        verbose=True,
        limit=3,
        loqi=True,
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
    assert "--loqi" in calls[0]
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
    def fake_run(*args, **_):
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
    def fake_run(*args, **_):
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


def test_run_reasoner_rpc_logs_trace_and_variables_on_error(
    monkeypatch, caplog
) -> None:
    def fake_rpc_call(*_, **__):
        raise RpcError(
            "reason failed: boom",
            code=500,
            data={
                "exceptionName": "java.lang.IllegalStateException",
                "rootCauseMessage": "boom",
                "stackTrace": "java.lang.IllegalStateException: boom\n\tat demo.Main",
                "partialTrace": {"branchResult": "Error", "elements": []},
                "variables": {"x": "1", "state": "failed"},
            },
        )

    monkeypatch.setattr("src.tpg_domain.rpc._rpc_call", fake_rpc_call)

    with caplog.at_level(logging.ERROR, logger="src.tpg_domain.rpc"):
        result = solve_reasoning_rpc("domain", "generated.loqi")

    assert result is None
    assert (
        "tpg_domain reason via JSON-RPC failed: reason failed: boom" in caplog.text
    )
    assert (
        "Server exception java.lang.IllegalStateException: boom\njava.lang.IllegalStateException: boom\n\tat demo.Main"
        in caplog.text
    )
    assert 'Trace:\n{\n  "branchResult": "Error",\n  "elements": []\n}' in caplog.text
    assert 'Variables:\n{\n  "x": "1",\n  "state": "failed"\n}' in caplog.text


def test_parse_discover_tree_jsonl_builds_structured_result() -> None:
    raw_jsonl = "\n".join(
        [
            '{"type":"summary","found":2,"shown":1}',
            '{"type":"node","nodeType":"BranchResultNode","metadata":[{"name":"id","locCode":null,"value":"n1"},{"name":"line","locCode":null,"value":2}]}',
        ]
    )

    result = parse_discover_tree_jsonl(raw_jsonl)

    assert result == DiscoverTreeResult(
        found=2,
        shown=1,
        nodes=[
            TreeNode(
                node_type="BranchResultNode",
                metadata=[
                    TreeNodeMetadataEntry(name="id", loc_code=None, value="n1"),
                    TreeNodeMetadataEntry(name="line", loc_code=None, value=2),
                ],
            )
        ],
    )


def test_discover_tree_builds_repeated_meta_args_and_requests_jsonl(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_domain_cli(*args: str) -> str:
        calls.append(args)
        return '{"type":"summary","found":0,"shown":0}'

    monkeypatch.setattr("src.tpg_domain.cli._run_domain_cli", fake_run_domain_cli)

    result = discover_tree(
        "tree.loqi",
        [("id", "n1"), ("line", "2")],
        union=True,
        limit=5,
        debug_enabled=True,
    )

    assert result == DiscoverTreeResult(found=0, shown=0, nodes=[])
    assert calls[0][:2] == ("discover-tree", "tree.loqi")
    assert calls[0].count("--meta") == 2
    assert "id=n1" in calls[0]
    assert "line=2" in calls[0]
    assert "--union" in calls[0]
    assert calls[0][calls[0].index("--limit") + 1] == "5"
    assert "--debug" in calls[0]
    assert calls[0][calls[0].index("--format") + 1] == "jsonl"


def test_discover_tree_rpc_sends_meta_criteria_and_maps_nodes(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_rpc_call(route: str, method: str, params: dict) -> dict:
        captured["route"] = route
        captured["method"] = method
        captured["params"] = params
        return {
            "found": 1,
            "shown": 1,
            "nodes": [
                {
                    "nodeType": "QuestionNode",
                    "metadata": [{"name": "id", "locCode": None, "value": "q1"}],
                }
            ],
        }

    monkeypatch.setattr("src.tpg_domain.rpc._rpc_call", fake_rpc_call)

    result = discover_tree_rpc("tree.xml", [("id", "q1")], union=False, limit=10)

    assert captured["route"] == "/rpc/domain"
    assert captured["method"] == "discover-tree"
    params = captured["params"]
    assert isinstance(params, dict)
    assert params["meta"] == [{"name": "id", "value": "q1"}]
    assert params["union"] is False
    assert params["limit"] == 10
    assert "treeXml" in params
    assert "treeLoqi" not in params

    assert result == DiscoverTreeResult(
        found=1,
        shown=1,
        nodes=[
            TreeNode(
                node_type="QuestionNode",
                metadata=[TreeNodeMetadataEntry(name="id", loc_code=None, value="q1")],
            )
        ],
    )


def test_parse_discover_tree_jsonl_includes_children_when_present() -> None:
    raw_jsonl = (
        '{"type":"summary","found":1,"shown":1}\n'
        '{"type":"node","nodeType":"QuestionNode","metadata":[{"name":"id","locCode":null,"value":"q1"}],'
        '"children":{"total":2,"descriptors":[{"id":"r1"},{"skill":"check"}]}}'
    )

    result = parse_discover_tree_jsonl(raw_jsonl)

    assert result.nodes == [
        TreeNode(
            node_type="QuestionNode",
            metadata=[TreeNodeMetadataEntry(name="id", loc_code=None, value="q1")],
            children=TreeNodeChildren(
                total=2,
                descriptors=[
                    TreeNodeDescriptor(id="r1"),
                    TreeNodeDescriptor(skill="check"),
                ],
            ),
        )
    ]


def test_discover_tree_passes_children_flag(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_domain_cli(*args: str) -> str:
        calls.append(args)
        return '{"type":"summary","found":0,"shown":0}'

    monkeypatch.setattr("src.tpg_domain.cli._run_domain_cli", fake_run_domain_cli)

    discover_tree("tree.loqi", [("id", "n1")], children=True)

    assert "--children" in calls[0]


def test_discover_tree_rpc_sends_children_flag(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_rpc_call(_route: str, _method: str, params: dict) -> dict:
        captured["params"] = params
        return {"found": 0, "shown": 0, "nodes": []}

    monkeypatch.setattr("src.tpg_domain.rpc._rpc_call", fake_rpc_call)

    discover_tree_rpc("tree.loqi", [("id", "n1")], children=True)

    params = captured["params"]
    assert isinstance(params, dict)
    assert params["children"] is True


def test_query_expression_rpc_sends_loqi_flag_and_maps_objects_loqi(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_rpc_call(_route: str, _method: str, params: dict) -> dict:
        captured["params"] = params
        return {
            "objects": ["a"],
            "objectsLoqi": [{"name": "a", "loqi": "obj a : Demo {}"}],
        }

    monkeypatch.setattr("src.tpg_domain.rpc._rpc_call", fake_rpc_call)

    result = query_expression_rpc("generated.loqi", "$x->prop == 1", loqi=True)

    params = captured["params"]
    assert isinstance(params, dict)
    assert params["loqi"] is True
    assert result == ExpressionQueryResult(
        objects=["a"],
        objects_loqi={"a": "obj a : Demo {}"},
    )
