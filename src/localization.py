from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from pathlib import Path

RESOURCES_DIR = Path(__file__).parent / "resources"


class MessageBundle:
    """Набор локализованных строк из файлов ``<base_name>_<lang>.properties``."""

    def __init__(
        self,
        messages: Mapping[str, Mapping[str, str]],
        *,
        default_lang: str = "en",
    ) -> None:
        self.default_lang = default_lang
        self._messages = {lang: dict(entries) for lang, entries in messages.items()}

    @classmethod
    def load(
        cls,
        base_name: str,
        *,
        directory: Path = RESOURCES_DIR,
        default_lang: str = "en",
    ) -> MessageBundle:
        messages = {
            file.stem.removeprefix(f"{base_name}_"): parse_properties(
                file.read_text(encoding="utf-8")
            )
            for file in sorted(directory.glob(f"{base_name}_*.properties"))
        }
        return cls(messages, default_lang=default_lang)

    @property
    def languages(self) -> tuple[str, ...]:
        return tuple(self._messages)

    def get(self, key: str, lang: str) -> str | None:
        return self._messages.get(lang, {}).get(key)

    def translate(self, key: str, lang: str | None = None) -> str:
        """
        Возвращает локализованную строку.
        Фолбэк: выбранный язык → default_lang → сам ключ.
        """
        return (
            self.get(key, lang or self.default_lang)
            or self.get(key, self.default_lang)
            or key
        )


@cache
def load_bundle(base_name: str) -> MessageBundle:
    return MessageBundle.load(base_name)


def parse_properties(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result
