import json
import logging
import subprocess
from pathlib import Path
from typing import Any

m2_repo = (
    Path.home() / ".m2" / "repository" / "org" / "vstu" / "meaningtree" / "application" / "1.0-SNAPSHOT"
)
JAR_PATH = m2_repo / "application-1.0-SNAPSHOT.jar"
JAVA_EXECUTABLE = "java"
JAR_RUN = [JAVA_EXECUTABLE, "-jar", JAR_PATH]


logger = logging.getLogger(__name__)


def to_dict(language: str, code: str) -> dict[str, Any] | None:
    """Convert code from language to dict representation using meaning tree

    Args:
        language: The source programming language (e.g., 'java', 'python', 'cpp')
        code: The code to convert

    Returns:
        Dict representation of the code's meaning tree or None if conversion failed
    """
    json_output = _run_serialize(code, language)
    if not json_output:
        return None
    return _parse_json(json_output)


def to_tokens(
    from_language: str, code: str, to_language: str | None = None,
) -> dict[str, Any] | None:
    """Tokenize source code into a structured representation

    Args:
        from_language: The source programming language (e.g., 'java', 'python', 'cpp')
        code: The code to tokenize
        to_language: Optional target language to map tokens into (if supported).
            If None, tokens remain in the source language context.

    Returns:
        Dict representation of the tokenized code, or None if tokenization failed
    """
    json_output = _run_tokenize(code, from_language, to_language)
    if not json_output:
        return None
    return _parse_json(json_output)


def convert(
    code: str, from_language: str, to_language: str, source_map: bool = False,
) -> str | dict[str, Any] | None:
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
    output = _run_convert(code, from_language, to_language, source_map)
    if not output:
        return None
    if source_map:
        return _parse_json(output)
    return output


def node_hierarchy() -> dict[str, list[str]]:
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
        result = subprocess.run(  # noqa: S603
            [*JAR_RUN, *args],
            input=stdin_data,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.exception("Error calling Java application")
        logger.error("Error output: %s", e.stderr)  # noqa: TRY400
        return None


def _run_serialize(code: str, source_lang: str, target_lang: str = "json") -> str | None:
    return _run_meaning_tree(
        "translate",
        "--from",
        source_lang,
        "--serialize",
        target_lang,
        "-",
        stdin_data=code,
    )


def _run_tokenize(code: str, source_lang: str, target_lang: str | None = None) -> str | None:
    if target_lang is None:
        conv_args = ["--tokenize-noconvert"]
    else:
        conv_args = ["--to", target_lang, "--tokenize"]
    return _run_meaning_tree(
        "translate",
        "--from",
        source_lang,
        *conv_args,
        "-",
        stdin_data=code,
    )


def _run_convert(
    code: str, source_lang: str, target_lang: str, source_map: bool = False,
) -> str | None:
    return _run_meaning_tree(
        "translate",
        "--from",
        source_lang,
        "--to",
        target_lang,
        *(["--source-map"] if source_map else []),
        "-",
        stdin_data=code,
    )


def _parse_json(json_data: str) -> dict[str, Any] | None:
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
