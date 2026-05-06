import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from src.env import TPG_CLI_DEBUG_ENV_VAR, env_flag

type TpgProject = Literal["its_DomainModel", "its_Reasoner"]
type DomainBuildMethod = Literal["LOQI", "RDF"]
type ReasoningResultFormat = Literal["raw", "loqi"]

VERSION: dict[TpgProject, str] = {
    "its_DomainModel": "3.0.0-alpha.7",
    "its_Reasoner": "3.0.0-alpha.3"
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
) -> bool:
    """Validate a DomainSolvingModel directory through its_DomainModel CLI."""
    return _run_domain_cli_bool(
        "validate-dsm",
        str(model_dir),
        "--build-method",
        build_method,
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
        *(["--separate-class-property-values"] if separate_class_property_values else []),
    )


def solve_reasoning(
    model_dir: str | Path,
    domain_loqi: str | Path,
    *,
    tag: str | None = None,
    tree: str | None = None,
    verbose: bool = False,
    result_format: ReasoningResultFormat = "raw",
) -> str | None:
    """Run its_Reasoner reasoning for a specific domain LOQI.

    ``result_format="raw"`` returns the CLI trace from stdout.
    ``result_format="loqi"`` returns the exported specific domain LOQI after reasoning.
    """
    args = [
        "reason",
        str(model_dir),
        str(domain_loqi),
        *_tag_args(tag),
        *_value_option("--tree", tree),
        *(["--verbose"] if verbose else []),
    ]
    if result_format == "raw":
        return _run_reasoner_cli(*args)

    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "reasoning-result.loqi"
        raw_result = _run_reasoner_cli(*args, "--export-domain", str(output))
        if raw_result is None:
            return None
        if not output.exists():
            logger.error("its_Reasoner CLI did not create exported LOQI: %s", output)
            return None
        return output.read_text(encoding="utf-8")


def solve_reasoning_result(
    model_dir: str | Path,
    domain_loqi: str | Path,
    *,
    tag: str | None = None,
    tree: str | None = None,
    verbose: bool = False,
) -> bool | None:
    """Run reasoning and return parsed Result value from the raw trace."""
    raw_result = solve_reasoning(
        model_dir,
        domain_loqi,
        tag=tag,
        tree=tree,
        verbose=verbose,
        result_format="raw",
    )
    if raw_result is None:
        return None
    return extract_reasoning_result(raw_result)


def extract_reasoning_result(raw_trace: str) -> bool | None:
    """Extract ``Result: ...`` from a reasoner trace.

    true/correct -> True, false/error -> False, null or missing result -> None.
    Matching is case-insensitive.
    """
    match = re.search(r"(?im)^\s*Result:\s*(true|false|null|correct|error)\s*$", raw_trace)
    if match is None:
        return None

    value = match.group(1).lower()
    if value in {"true", "correct"}:
        return True
    if value in {"false", "error"}:
        return False
    return None


def _run_domain_cli_bool(*args: str) -> bool:
    return _run_domain_cli(*args) is not None


def _run_domain_cli_text_or_bool(output: str | Path | None, *args: str) -> str | bool | None:
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
        if _debug_enabled():
            _print_cli_streams(e.stdout, e.stderr)
        elif e.stderr:
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
