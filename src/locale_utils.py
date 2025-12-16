from pathlib import Path


class Locales:
    def __init__(self, base_name: str = "messages", default_lang: str = "en"):
        """
        base_name: префикс файлов (messages_ru.properties)
        default_lang: язык по умолчанию
        """
        self.default_lang = default_lang
        self._data: dict[str, dict[str, str]] = {}

        self._load_locales(base_name)

    def _load_locales(self, base_name: str) -> None:
        base_dir = Path(__file__).parent / "locales"

        for file in base_dir.glob(f"{base_name}_*.properties"):
            lang = file.stem.split("_")[-1]
            self._data[lang] = self._parse_properties(file)

    @staticmethod
    def _parse_properties(path: Path) -> dict[str, str]:
        result = {}

        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()

        return result

    def get(self, key: str, lang: str | None = None) -> str:
        """
        Возвращает локализованную строку.
        Фолбэк: выбранный язык → default_lang → сам ключ.
        """
        lang = lang or self.default_lang

        return (
            self._data.get(lang, {}).get(key)
            or self._data.get(self.default_lang, {}).get(key)
            or key
        )
