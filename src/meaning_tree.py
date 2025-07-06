import tempfile
import subprocess
import json
import os
import logging
from pathlib import Path
from typing import Dict, Optional, Any, Generator
from contextlib import contextmanager


JAR_PATH = Path("meaning_tree/modules/application/target/application-1.0-SNAPSHOT.jar")

logger = logging.getLogger(__name__)


def to_dict(language: str, code: str) -> Optional[Dict[str, Any]]:
    """Convert code from language to dict representation using meaning tree

    Args:
        language: The source programming language (e.g., 'java', 'python', 'cpp')
        code: The code to convert

    Returns:
        Dict representation of the code's meaning tree or None if conversion failed
    """
    with _temp_file(code, language) as temp_file_path:
        json_output = _run_translator(temp_file_path, language)
        if not json_output:
            return None

        return _parse_json(json_output)


@contextmanager
def _temp_file(content: str, extension: str) -> Generator[Path, None, None]:
    """Create a temporary file with the given content and extension

    Args:
        content: Content to write to the temporary file
        extension: File extension for the temporary file

    Yields:
        Path: Path to the temporary file
    """
    temp_path = Path(tempfile.mktemp(suffix=f".{extension}"))
    try:
        temp_path.write_text(content)
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)


def _run_translator(
    input_file: Path, source_lang: str, target_lang: str = "json"
) -> Optional[str]:
    """Run the meaning tree translator on the given input file

    Args:
        input_file: Path to the input file
        source_lang: Source programming language
        target_lang: Target output format, defaults to 'json'

    Returns:
        Output of the translator or None if translation failed
    """
    jar_path = JAR_PATH

    try:
        result = subprocess.run(
            [
                "java",
                "-jar",
                str(jar_path),
                "translate",
                "--from",
                source_lang,
                "--serialize",
                target_lang,
                str(input_file),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Error calling Java application: {e}")
        logger.error(f"Error output: {e.stderr}")
        return None


def _parse_json(json_data: str) -> Optional[Dict[str, Any]]:
    """Parse JSON data into a dictionary

    Args:
        json_data: JSON string to parse

    Returns:
        Parsed JSON data or None if parsing failed
    """
    try:
        return json.loads(json_data)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON output: {e}")
        return None
