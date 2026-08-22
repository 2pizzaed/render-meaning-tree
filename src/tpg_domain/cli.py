from __future__ import annotations

import json
import logging
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from src.env import TPG_CLI_DEBUG_ENV_VAR, env_flag

from .models import (
    DiscoverTreeResult,
    DomainBuildMethod,
    ExpressionQueryResult,
    ReasoningResult,
    TpgProject,
    _format_human_value,
    parse_discover_tree_jsonl,
    parse_expression_query_jsonl,
    parse_reasoning_jsonl,
)

VERSION: dict[TpgProject, str] = {
    "its_DomainModel": "3.0.0-rc.1",
    "its_Reasoner": "3.0.0-rc.1",
}

logger = logging.getLogger(__name__)


def make_path(project: TpgProject) -> list[str | Path]:
    version = VERSION[project]
    m2_repo = (
        Path.home()
        / ".m2"
        / "repository"
        / "com"
        / "github"
        / "CompPrehension"
        / project
        / VERSION[project]
    )
    JAR_PATH = m2_repo / f"{project}-{version}-all.jar"
    JAVA_EXECUTABLE = "java"
    JAR_RUN = [
        JAVA_EXECUTABLE,
        "-Dfile.encoding=UTF-8",
        "-Dstdin.encoding=UTF-8",
        "-Dstdout.encoding=UTF-8",
        "-Dstderr.encoding=UTF-8",
        "-jar",
        JAR_PATH,
    ]
    return JAR_RUN


def validate_domain_solving_model(
    model_dir: str | Path,
    build_method: DomainBuildMethod = "LOQI",
    *,
    debug_enabled: bool = False,
) -> bool:
    """Validate a DomainSolvingModel directory through its_DomainModel CLI."""
    return _run_domain_cli_bool(
        "validate-dsm",
        str(model_dir),
        "--build-method",
        build_method,
        *(["--debug"] if debug_enabled else []),
    )


def validate_domain_loqi(
    domain_loqi: str | Path,
    model_dir: str | Path,
    tag: str | None = None,
    print_merged_loqi: bool = False,
) -> bool:
    """Validate a domain LOQI file in the context of a DomainSolvingModel."""
    return _run_domain_cli_bool(
        "validate-domain-loqi",
        str(domain_loqi),
        str(model_dir),
        *(_tag_args(tag)),
        *(["--print-merged-loqi"] if print_merged_loqi else []),
    )


def tree_loqi_to_xml(
    tree_loqi: str | Path,
    *,
    output: str | Path | None = None,
    model_dir: str | Path | None = None,
    tag: str | None = None,
    cdata_expressions: bool = True,
) -> str | bool | None:
    """Convert a LOQI thought process tree to XML through its_DomainModel CLI.

    If ``output`` is provided, returns True/False by the CLI exit status.
    Otherwise returns XML text from stdout, or None on failure.
    """
    return _run_domain_cli_text_or_bool(
        output,
        "tree-loqi-to-xml",
        str(tree_loqi),
        *(_path_option("--model-dir", model_dir)),
        *(_tag_args(tag)),
        *(["--cdata-expressions"] if cdata_expressions else []),
        *(_path_option("-o", output)),
    )


def discover_tree(
    tree_file: str | Path,
    meta: Sequence[tuple[str, str]],
    *,
    union: bool = False,
    limit: int | None = None,
    debug_enabled: bool = False,
    children: bool = False,
) -> DiscoverTreeResult | None:
    """Search decision tree nodes by metadata through its_DomainModel CLI.

    ``tree_file`` is LOQI/TPG or XML, auto-detected by extension. ``meta`` is a
    sequence of (name, value) criteria; combined with AND unless ``union`` is set.
    If a "line" criterion is present, debug metadata is built automatically even
    without ``debug_enabled``. If ``children`` is set, each matched node's
    :attr:`TreeNode.children` reports its immediate (depth-1) child nodes.
    """
    args = [
        "discover-tree",
        str(tree_file),
        *[arg for name, value in meta for arg in ("--meta", f"{name}={value}")],
        *(["--union"] if union else []),
        *([] if limit is None else ["--limit", str(limit)]),
        *(["--debug"] if debug_enabled else []),
        *(["--children"] if children else []),
        "--format",
        "jsonl",
    ]

    raw_result = _run_domain_cli(*args)
    if raw_result is None:
        return None
    return parse_discover_tree_jsonl(raw_result)


def domain_to_rdf(
    model_dir: str | Path,
    *,
    build_method: DomainBuildMethod = "LOQI",
    tag: str | None = None,
    domain_loqi: str | Path | None = None,
    output: str | Path | None = None,
    base_prefix: str | None = None,
    old_nary_compat: bool = False,
) -> str | bool | None:
    """Convert a concrete domain from LOQI/DSM to RDF Turtle.

    If ``output`` is provided, returns True/False by the CLI exit status.
    Otherwise returns Turtle text from stdout, or None on failure.
    """
    return _run_domain_cli_text_or_bool(
        output,
        "domain-to-rdf",
        str(model_dir),
        "--build-method",
        build_method,
        *(_tag_args(tag)),
        *(_path_option("--domain-loqi", domain_loqi)),
        *(_path_option("--output", output)),
        *(_value_option("--base-prefix", base_prefix)),
        *(["--old-nary-compat"] if old_nary_compat else []),
    )


def rdf_to_domain_loqi(
    model_dir: str | Path,
    rdf_ttl: str | Path,
    *,
    build_method: DomainBuildMethod = "LOQI",
    tag: str | None = None,
    domain_loqi: str | Path | None = None,
    output: str | Path | None = None,
    base_prefix: str | None = None,
    old_nary_compat: bool = False,
    throw_invalid_meta: bool = False,
    separate_metadata: bool = False,
    separate_class_property_values: bool = False,
) -> str | bool | None:
    """Convert RDF Turtle data to domain LOQI.

    If ``output`` is provided, returns True/False by the CLI exit status.
    Otherwise returns LOQI text from stdout, or None on failure.
    """
    return _run_domain_cli_text_or_bool(
        output,
        "rdf-to-domain-loqi",
        str(model_dir),
        str(rdf_ttl),
        "--build-method",
        build_method,
        *(_tag_args(tag)),
        *(_path_option("--domain-loqi", domain_loqi)),
        *(_path_option("--output", output)),
        *(_value_option("--base-prefix", base_prefix)),
        *(["--old-nary-compat"] if old_nary_compat else []),
        *(["--throw-invalid-meta"] if throw_invalid_meta else []),
        *(["--separate-metadata"] if separate_metadata else []),
        *(
            ["--separate-class-property-values"]
            if separate_class_property_values
            else []
        ),
    )


def solve_reasoning(
    model_dir: str | Path,
    domain_loqi: str | Path,
    *,
    tag: str | None = None,
    tree: str | None = None,
    verbose: bool = False,
    json_trace: bool = False,
    debug_enabled: bool = False,
    export_domain: bool = False,
    reasoner_output_stream: TextIO | None = None,
    time_limit_seconds: int | None = None
) -> ReasoningResult | None:
    """Run its_Reasoner reasoning for a specific domain LOQI.

    The reasoner is always called with ``--format jsonl`` and returns a parsed
    :class:`ReasoningResult`. Trace is text by default; pass ``json_trace=True``
    to request structured JSON trace values from the CLI.

    If ``reasoner_output_stream`` is provided, ``reasoner-output`` JSONL events
    are printed to it while being collected in the result.
    """
    args = [
        "reason",
        str(model_dir),
        str(domain_loqi),
        *_tag_args(tag),
        *_value_option("--tree", tree),
        *(["--verbose"] if verbose else []),
        "--format",
        "jsonl",
        *(["--json-trace"] if json_trace else []),
        *(["--export-domain", "-"] if export_domain else []),
        *(["--debug"] if debug_enabled else []),
        *(["--time-limit", str(time_limit_seconds)] if time_limit_seconds is not None else []),
    ]

    raw_result = _run_reasoner_cli(*args)
    if raw_result is None:
        return None

    return parse_reasoning_jsonl(
        raw_result,
        reasoner_output_stream=reasoner_output_stream,
    )


def solve_reasoning_result(
    model_dir: str | Path,
    domain_loqi: str | Path,
    *,
    tag: str | None = None,
    tree: str | None = None,
    verbose: bool = False,
    reasoner_output_stream: TextIO | None = None,
    time_limit_seconds: int | None = None
) -> bool | None:
    """Run reasoning and return parsed result value."""
    result = solve_reasoning(
        model_dir,
        domain_loqi,
        tag=tag,
        tree=tree,
        verbose=verbose,
        reasoner_output_stream=reasoner_output_stream,
        time_limit_seconds=time_limit_seconds
    )
    if not isinstance(result, ReasoningResult):
        return None
    return result.result


def query_expression(
    domain_loqi: str | Path,
    expression: str,
    *,
    model_dir: str | Path | None = None,
    tag: str | None = None,
    debug_enabled: bool = False,
    trace: bool = False,
    verbose: bool = False,
    json_trace: bool = False,
    limit: int | None = None,
    loqi: bool = False,
    time_measure: bool = False,
    reasoner_output_stream: TextIO | None = None,
) -> ExpressionQueryResult | None:
    """Run its_Reasoner expression-query against a specific LOQI domain.

    If ``loqi`` is set, each found object is additionally serialized into LOQI
    text (via DomainModel's LOQI writer) and reported in the result's
    ``objects_loqi`` mapping.
    """
    args = [
        "expression-query",
        *([str(model_dir)] if model_dir is not None else []),
        str(domain_loqi),
        expression,
        *_tag_args(tag),
        *(["--debug"] if debug_enabled else []),
        *(["--trace"] if trace else []),
        *(["--verbose"] if verbose else []),
        *(["--json-trace"] if json_trace else []),
        *([] if limit is None else ["--limit", str(limit)]),
        *(["--loqi"] if loqi else []),
        *(["--time-measure"] if time_measure else []),
        "--format",
        "jsonl",
    ]

    raw_result = _run_reasoner_cli(*args)
    if raw_result is None:
        return None
    return parse_expression_query_jsonl(
        raw_result,
        reasoner_output_stream=reasoner_output_stream,
    )


def _run_domain_cli_bool(*args: str) -> bool:
    return _run_domain_cli(*args) is not None


def _run_domain_cli_text_or_bool(
    output: str | Path | None, *args: str
) -> str | bool | None:
    result = _run_domain_cli(*args)
    if output is not None:
        return result is not None
    return result


def _run_domain_cli(*args: str) -> str | None:
    return _run_tpg_cli("its_DomainModel", *args)


def _run_reasoner_cli(*args: str) -> str | None:
    return _run_tpg_cli("its_Reasoner", *args)


def _run_tpg_cli(project: TpgProject, *args: str) -> str | None:
    try:
        prepared_args = [*make_path(project), *args]
        debug = _debug_enabled()
        if debug:
            print(f"Running command: {' '.join(map(str, prepared_args))}")
        result = subprocess.run(
            prepared_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        if debug:
            _print_cli_streams(result.stdout, result.stderr)
        elif result.stderr:
            logger.warning("%s CLI error output: %s", project, result.stderr)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error("Error calling %s CLI", project)
        _log_cli_json_event_value(
            e.stdout,
            e.stderr,
            event_types={"trace", "partial-trace", "partial-expression-trace"},
            label="Trace",
        )
        _log_cli_json_event_value(
            e.stdout,
            e.stderr,
            event_types={"variables"},
            label="Variables",
        )
        parsed_errors = _log_cli_json_errors(project, e.stdout, e.stderr)

        if _debug_enabled() and not parsed_errors:
            _print_cli_streams(e.stdout, e.stderr)
        elif e.stderr and not parsed_errors:
            logger.error("Error output: %s", e.stderr)

        if not _debug_enabled() and e.stdout:
            logger.debug("Output before failure: %s", e.stdout)

        return None
    except OSError as e:
        logger.error("Could not start %s CLI: %s", project, e)
        return None


def _debug_enabled() -> bool:
    return env_flag(TPG_CLI_DEBUG_ENV_VAR)


def _print_cli_streams(stdout: str | None, stderr: str | None) -> None:
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)


def _log_cli_json_errors(
    project: TpgProject, stdout: str | None, stderr: str | None
) -> bool:
    errors = [
        event
        for stream in (stderr, stdout)
        for event in _parse_jsonl_events(stream)
        if event.get("type") == "error"
    ]
    for event in errors:
        exception_name = event.get("exceptionName")
        message = event.get("message")
        stack_trace = event.get("stackTrace")
        header = f"{project} CLI error"
        if exception_name:
            header += f" {exception_name}"
        if message:
            header += f": {message}"
        if stack_trace:
            logger.error("%s\n%s", header, stack_trace)
        else:
            logger.error("%s", header)
    return bool(errors)


def _log_cli_json_event_value(
    stdout: str | None,
    stderr: str | None,
    *,
    event_types: set[str],
    label: str,
) -> None:
    for stream in (stderr, stdout):
        for event in _parse_jsonl_events(stream):
            if event.get("type") in event_types:
                value = event.get("value")
                if value is not None:
                    logger.error("%s:\n%s", label, _format_human_value(value))
                    return


def _parse_jsonl_events(raw_jsonl: str | None) -> list[dict[str, Any]]:
    if not raw_jsonl:
        return []
    events: list[dict[str, Any]] = []
    for line in raw_jsonl.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _tag_args(tag: str | None) -> list[str]:
    return _value_option("--tag", tag)


def _path_option(name: str, value: str | Path | None) -> list[str]:
    if value is None:
        return []
    return [name, str(value)]


def _value_option(name: str, value: str | None) -> list[str]:
    if value is None:
        return []
    return [name, value]
