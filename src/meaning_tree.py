import json
import logging
import subprocess
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

JAR_PATH = Path("meaning_tree/modules/application/target/application-1.0-SNAPSHOT.jar")

logger = logging.getLogger(__name__)


def to_dict(language: str, code: str) -> dict[str, Any] | None:
    """Convert code from language to dict representation using meaning tree

    Args:
        language: The source programming language (e.g., 'java', 'python', 'cpp')
        code: The code to convert

    Returns:
        Dict representation of the code's meaning tree or None if conversion failed
    """
    with _temp_file(code, language) as temp_file_path:
        json_output = _run_serialize(temp_file_path, language)
        if not json_output:
            return None

        return _parse_json(json_output)


def to_tokens(
    from_language: str, code: str, to_language: str | None = None
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
    with _temp_file(code, from_language) as temp_file_path:
        json_output = _run_tokenize(temp_file_path, from_language, to_language)
        if not json_output:
            return None

        return _parse_json(json_output)


def convert(
    code: str, from_language: str, to_language: str, source_map: bool = False
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
    with _temp_file(code, from_language) as temp_file_path:
        output = _run_convert(temp_file_path, from_language, to_language, source_map)
        if not output:
            return None
        if source_map:
            return _parse_json(output)
        return output


@contextmanager
def _temp_file(content: str, extension: str) -> Generator[Path]:
    """Create a temporary file with the given content and extension

    Args:
        content: Content to write to the temporary file
        extension: File extension for the temporary file

    Yields:
        Path: Path to the temporary file
    """
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp_file:
        tmp_file.write(content.encode())
        temp_path = Path(tmp_file.name)
    try:
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)


def _run_meaning_tree(*args: str) -> str | None:
    jar_path = JAR_PATH

    try:
        result = subprocess.run(
            [  # noqa: S607
                "java",
                "-jar",
                str(jar_path),
                *args,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.exception("Error calling Java application")
        logger.error("Error output: %s", e.stderr)
        return None


def _run_serialize(
    input_file: Path, source_lang: str, target_lang: str = "json",
) -> str | None:
    """Run the meaning tree translator on the given input file

    Args:
        input_file: Path to the input file
        source_lang: Source programming language
        target_lang: Target output format, defaults to 'json'

    Returns:
        Output of the translator or None if translation failed
    """
    return _run_meaning_tree(
        "translate",
        "--from",
        source_lang,
        "--serialize",
        target_lang,
        str(input_file),
    )


def _run_tokenize(
    input_file: Path, source_lang: str, target_lang: str | None = None,
) -> str | None:
    if target_lang is None:
        conv_args = [
            "--tokenize-noconvert",
        ]
    else:
        conv_args = [
            "--to",
            target_lang,
            "--tokenize",
        ]
    return _run_meaning_tree(
        "translate",
        "--from",
        source_lang,
        *conv_args,
        str(input_file),
    )


def _run_convert(
    input_file: Path,
    source_lang: str,
    target_lang: str,
    source_map: bool = False,
) -> str | None:
    return _run_meaning_tree(
        "translate",
        "--from",
        source_lang,
        "--to",
        target_lang,
        *(["--source-map"] if source_map else []),
        str(input_file),
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
