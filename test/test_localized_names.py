from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

import pytest

from src.generator.pipeline import DomainDataGeneratorPipeline
from src.generator.utilities import code_snippet_to_pipeline, registry_to_loqi
from src.localization import MessageBundle, load_bundle, parse_properties
from src.serialization.localized_names import (
    TRACED_PREFIX_KEY,
    TRACED_SUFFIX_KEY,
    NameMetadata,
    NameParts,
    format_localized_name,
)
from src.serialization.loqi import (
    LoqiAdapterContext,
    LoqiMetadataEntry,
    LoqiObjectSpec,
    LoqiRenderResult,
    LoqiSerializer,
)

BUNDLE = MessageBundle(
    {
        "en": {
            "loop": "loop",
            "on_line": "on line",
            "function_call": "function call",
            "traced_prefix": "traced",
        },
        "ru": {"loop": "цикл", "on_line": "на строке", "traced_suffix": "в трассе"},
    }
)


def test_parse_properties_skips_comments_and_keeps_separators_in_value() -> None:
    assert parse_properties("# comment\n! other\n\nkey = a=b\nempty=\n") == {
        "key": "a=b",
        "empty": "",
    }


def test_message_bundle_translate_falls_back_to_default_language_then_key() -> None:
    assert BUNDLE.translate("loop", "ru") == "цикл"
    assert BUNDLE.translate("function_call", "ru") == "function call"
    assert BUNDLE.translate("missing", "ru") == "missing"
    assert BUNDLE.get("function_call", "ru") is None


def test_message_bundle_load_detects_languages_by_file_suffix(tmp_path: Path) -> None:
    (tmp_path / "names_en.properties").write_text("loop=loop\n", encoding="utf-8")
    (tmp_path / "names_ru.properties").write_text("loop=цикл\n", encoding="utf-8")
    (tmp_path / "other_en.properties").write_text("loop=other\n", encoding="utf-8")

    bundle = MessageBundle.load("names", directory=tmp_path)

    assert bundle.languages == ("en", "ru")
    assert bundle.translate("loop", "ru") == "цикл"


def test_definitions_bundles_share_keys_except_optional_affixes() -> None:
    bundle = load_bundle("definitions")
    optional = {TRACED_PREFIX_KEY, TRACED_SUFFIX_KEY}

    assert set(bundle.languages) == {"en", "ru"}
    assert _definition_keys(bundle, "en") - optional == _definition_keys(bundle, "ru") - optional


def test_format_localized_name_wraps_keyword_and_identifier() -> None:
    loop = NameParts(NameMetadata(trace_name="loop", keyword="while"))
    call = NameParts(NameMetadata("function_call"))

    assert format_localized_name(loop, BUNDLE, "ru", line=3) == "цикл <code>while</code> на строке 3"
    assert (
        format_localized_name(call, BUNDLE, "en", identifier="f<x>")
        == 'function call <code class="id">f&lt;x&gt;</code>'
    )


def test_format_localized_name_skips_affixes_missing_in_language() -> None:
    traced = NameParts(NameMetadata("loop"), prefix_key=TRACED_PREFIX_KEY, suffix_key=TRACED_SUFFIX_KEY)

    assert format_localized_name(traced, BUNDLE, "en", line=3) == "traced loop on line 3"
    assert format_localized_name(traced, BUNDLE, "ru", line=3) == "цикл на строке 3 в трассе"


class _NamedAdapter:
    def type_name(self, obj: object) -> str:
        return "Thing"

    def describe(self, obj: object, ctx: LoqiAdapterContext) -> LoqiObjectSpec:
        return LoqiObjectSpec()


def test_serializer_decorators_modify_copy_and_are_not_repeated() -> None:
    def decorator(result: LoqiRenderResult) -> None:
        for obj in result.objects:
            obj.metadata.append(LoqiMetadataEntry(name="decorated", value=True))

    serializer = LoqiSerializer(adapters_by_type={object: _NamedAdapter()}, decorators=(decorator,))
    serializer.serialize(object())

    first = serializer.render()
    second = serializer.render()

    assert first == second
    assert first.count("decorated = true") == 1
    assert serializer.objects[0].metadata == []


@pytest.fixture(scope="module")
def trace_pipeline() -> DomainDataGeneratorPipeline:
    code = dedent(
        """\
        def foo(a):
            return a

        i = 0
        while foo(i):
            i += 1
            if i > 3:
                break
        """
    )
    return code_snippet_to_pipeline(code)


@pytest.fixture(scope="module")
def trace_loqi(trace_pipeline: DomainDataGeneratorPipeline) -> str:
    _, loqi = registry_to_loqi(trace_pipeline.flatten_results()[0])
    return loqi


@pytest.fixture(scope="module")
def lines(trace_pipeline: DomainDataGeneratorPipeline) -> dict[str, int]:
    """Номера строк в коде, сгенерированном Meaning Tree (его и видит студент)."""
    rendered = trace_pipeline.code.code.splitlines()
    return {
        marker: next(number for number, text in enumerate(rendered, 1) if text.strip().startswith(marker))
        for marker in ("while", "break")
    }


def _object_metadata(loqi: str, object_id: str) -> dict[str, str]:
    match = re.search(rf"^obj {re.escape(object_id)} : .*?^\}}(?P<meta>[^\n]*)$", loqi, re.MULTILINE | re.DOTALL)
    assert match is not None, object_id
    return dict(re.findall(r'([\w.]+) = "((?:[^"\\]|\\.)*)"', match["meta"]))


def test_construct_gets_localized_name_with_keyword_and_line(
    trace_loqi: str, lines: dict[str, int]
) -> None:
    metadata = _object_metadata(trace_loqi, "construct_while_structure_ast54")

    assert metadata == {
        "EN.localizedName": f"loop <code>while</code> on line {lines['while']}",
        "RU.localizedName": f"цикл <code>while</code> на строке {lines['while']}",
        "pronoun": "he",
    }


def test_action_prefers_own_metadata_over_construct(
    trace_loqi: str, lines: dict[str, int]
) -> None:
    metadata = _object_metadata(trace_loqi, "while_structure_action_cond_ast28")

    assert metadata["EN.localizedName"] == f"condition on line {lines['while']}"
    assert metadata["pronoun"] == "it"


def test_boundary_action_falls_back_to_construct_with_same_ast_id(trace_loqi: str) -> None:
    assert _object_metadata(trace_loqi, "while_structure_action_BEGIN_ast54") == _object_metadata(
        trace_loqi, "construct_while_structure_ast54"
    )


def test_function_call_name_includes_identifier(
    trace_loqi: str, lines: dict[str, int]
) -> None:
    metadata = _object_metadata(trace_loqi, "construct_func_call_structure_ast28")

    assert metadata["EN.localizedName"] == (
        f'function call <code class=\\"id\\">foo</code> on line {lines["while"]}'
    )


def test_atomic_inline_action_uses_inline_rule_metadata(
    trace_loqi: str, lines: dict[str, int]
) -> None:
    metadata = _object_metadata(trace_loqi, "block_structure_action_first_ast46")

    assert metadata["EN.localizedName"] == f"loop break on line {lines['break']}"
    assert metadata["pronoun"] == "she"


def test_trace_act_wraps_action_name_with_traced_affixes(trace_loqi: str) -> None:
    action_metadata = _object_metadata(trace_loqi, "global_statements_structure_action_BEGIN_ast69")
    metadata = _object_metadata(trace_loqi, "act_root")

    assert metadata == {
        "EN.localizedName": f"traced {action_metadata['EN.localizedName']}",
        "RU.localizedName": f"{action_metadata['RU.localizedName']} в трассе",
        "pronoun": action_metadata["pronoun"],
    }


def _definition_keys(bundle: MessageBundle, lang: str) -> set[str]:
    return set(bundle._messages[lang])  # pyright: ignore[reportPrivateUsage]
