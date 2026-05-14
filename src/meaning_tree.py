import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.env import MEANING_TREE_CLI_DEBUG_ENV_VAR, env_flag
from src.types import JSON, MeaningTree, SourceMap, TokenList

m2_repo = (
    Path.home() / ".m2" / "repository" / "org" / "vstu" / "meaningtree" / "application" / "1.0-SNAPSHOT"
)
JAR_PATH = m2_repo / "application-1.0-SNAPSHOT.jar"
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
logger = logging.getLogger(__name__)


def serialize_config(config: JSON | None = None) -> list[str]:
    if not config:
        return []
    return ["--config", json.dumps(config, ensure_ascii=False)]


def to_dict(language: str, code: str, config: JSON | None = None) -> MeaningTree | None:
    """Convert code from language to Meaning Tree

    Args:
        language: The source programming language (e.g., 'java', 'python', 'cpp')
        code: The code to convert

    Returns:
        Dict representation of the code's meaning tree or None if conversion failed
    """
    json_output = _run_serialize(code, language, config=config)
    if not json_output:
        return None
    return _parse_json(json_output) # type: ignore


def to_dot(language: str, code: str, config: JSON | None = None) -> str | None:
    """Convert code from language to string dot graph representation using meaning tree

    Args:
        language: The source programming language (e.g., 'java', 'python', 'cpp')
        code: The code to convert

    Returns:
        dot language graph code
    """
    output = _run_serialize(code, language, "dot", config=config)
    if not output:
        return None
    return output


def to_tokens(
    from_language: str, code: str, to_language: str | None = None, config: JSON | None = None
) -> TokenList | None:
    """Tokenize source code into a structured representation

    Args:
        from_language: The source programming language (e.g., 'java', 'python', 'cpp')
        code: The code to tokenize
        to_language: Optional target language to map tokens into (if supported).
            If None, tokens remain in the source language context.

    Returns:
        Dict representation of the tokenized code, or None if tokenization failed
    """
    json_output = _run_tokenize(code, from_language, to_language, config=config)
    if not json_output:
        return None
    return _parse_json(json_output) # type: ignore


def convert(
    code: str, from_language: str, to_language: str, source_map: bool = False, config: JSON | None = None
) -> str | SourceMap | None:
    """Convert code between programming languages or produce a source map

    Args:
        code: The code to convert
        from_language: The source programming language
        to_language: The target programming language
        source_map: If True, return a JSON-serializable dict describing
            the source map of code transformations instead of converted code

    Returns:
        Converted code as a string if source_map is False,
        dict representation of the source map if source_map is True,
        or None if conversion failed
    """
    output = _run_convert(code, from_language, to_language, source_map, config=config)
    if not output:
        return None
    if source_map:
        return _parse_json(output) # type: ignore
    return output


def generate(
    ast: str,
    to_language: str,
    format: str = "json",
    source_map: bool = False, config: JSON | None = None
) -> str | dict[str, Any] | None:
    """Convert code between programming languages or produce a source map

    Args:
        ast: Meaning Tree representation in specified format
        format: Meaning Tree representation format
        to_language: The target programming language
        source_map: If True, return a JSON-serializable dict describing
            the source map of code transformations instead of converted code

    Returns:
        Converted code as a string if source_map is False,
        dict representation of the source map if source_map is True,
        or None if conversion failed
    """
    output = _run_generate(ast, format, to_language, source_map, config=config)
    if not output:
        return None
    if source_map:
        return _parse_json(output)
    return output


def node_hierarchy() -> JSON:
    """Retrieve the node hierarchy from the meaning tree application

    Returns:
        Dict representation of the node hierarchy or None if retrieval failed
    """
    output = _run_meaning_tree("node-hierarchy")
    if not output:
        return {}
    json = _parse_json(output)
    if not json:
        return {}
    return json



def _run_meaning_tree(*args: str, stdin_data: str | None = None) -> str | None:
    try:
        prepared_args = [*JAR_RUN, *args]
        debug = _debug_enabled()
        if debug:
            print(f"Running command: {' '.join(map(str, prepared_args))}")
        result = subprocess.run(
            prepared_args,
            input=stdin_data,
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True,
        )
        if debug:
            _print_cli_streams(result.stdout, result.stderr)
        elif not result.stdout and result.stderr:
            logger.error("Meaning Tree error output: %s", result.stderr)
            return None
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.exception("Error calling Java application")
        if _debug_enabled():
            _print_cli_streams(e.stdout, e.stderr)
        elif e.stderr:
            logger.error("Error output: %s", e.stderr)
        if not _debug_enabled() and e.stdout:
            logger.debug("Output before failure: %s", e.stdout)
        return None


def _debug_enabled() -> bool:
    return env_flag(MEANING_TREE_CLI_DEBUG_ENV_VAR)


def _print_cli_streams(stdout: str | None, stderr: str | None) -> None:
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)


def _run_serialize(code: str, source_lang: str, target_lang: str = "json", config: JSON | None = None) -> str | None:
    return _run_meaning_tree(
        "translate",
        "--from",
        source_lang,
        "--serialize",
        target_lang,
        *serialize_config(config),
        "-",
        stdin_data=code,
    )


def _run_tokenize(code: str, source_lang: str,
                  target_lang: str | None = None, config: JSON | None = None) -> str | None:
    if target_lang is None:
        conv_args = ["--tokenize-noconvert"]
    else:
        conv_args = ["--to", target_lang, "--tokenize"]
    return _run_meaning_tree(
        "translate",
        "--from",
        source_lang,
        *conv_args,
        *serialize_config(config),
        "-",
        stdin_data=code,
    )


def _run_convert(
    code: str, source_lang: str, target_lang: str, source_map: bool = False,
    config: JSON | None = None
) -> str | None:
    return _run_meaning_tree(
        "translate",
        "--from",
        source_lang,
        "--to",
        target_lang,
        *(["--source-map"] if source_map else []),
        *serialize_config(config),
        "-",
        stdin_data=code,
    )

def _run_generate(
    ast: str,
    format: str,
    target_lang: str,
    source_map: bool = False,
    config: JSON | None = None
) -> str | None:
    return _run_meaning_tree(
        "generate",
        "--to",
        target_lang,
        "--format",
        format,
        *(["--source-map"] if source_map else []),
        *serialize_config(config),
        "-",
        stdin_data=ast,
    )


def _parse_json(json_data: str) -> JSON | None:
    """Parse JSON data into a dictionary

    Args:
        json_data: JSON string to parse

    Returns:
        Parsed JSON data or None if parsing failed
    """
    try:
        return json.loads(json_data)
    except json.JSONDecodeError:
        logger.exception("Error parsing JSON output: %s")
        return None
