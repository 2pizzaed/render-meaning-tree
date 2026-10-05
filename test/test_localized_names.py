from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

import pytest

from src.generator.pipeline import SituationRegistry
from src.generator.utilities import code_snippet_to_registry, registry_to_loqi
from src.localization import MessageBundle, load_bundle, parse_properties
from src.model.rules import Metadata
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
            "begin": "begin of",
        },
        "ru": {"loop": "цикл", "on_line": "на строке", "traced_suffix": "в трассе", "begin": "начало"},
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


def test_format_localized_name_puts_boundary_before_name_declined_in_russian() -> None:
    begin = NameParts(
        NameMetadata("loop", keyword="while"),
        prefix_key=TRACED_PREFIX_KEY,
        suffix_key=TRACED_SUFFIX_KEY,
        boundary_key="begin",
    )

    assert format_localized_name(begin, BUNDLE, "en", line=3) == "traced begin of loop <code>while</code> on line 3"
    assert format_localized_name(begin, BUNDLE, "ru", line=3) == "начало цикла <code>while</code> на строке 3 в трассе"


def test_raw_explanation_replaces_composed_name_and_keeps_other_placeholders() -> None:
    raw = NameMetadata(None, keyword="while", raw_explanation="${translate(\"begin\")} ${translate('loop')}[case='р'] ${X}")
    parts = NameParts(raw, prefix_key=TRACED_PREFIX_KEY, boundary_key="begin")

    assert format_localized_name(parts, BUNDLE, "en", line=3) == "traced begin of loop ${X}"
    assert format_localized_name(parts, BUNDLE, "ru", line=3) == "начало цикла ${X}"
    assert parts.pronoun is None


def test_raw_explanation_keeps_unresolved_templating_verbatim() -> None:
    raw = "${X}[case='р'] $Y \\$Z ${translate(1, 2)} ${f('a')}"

    assert format_localized_name(NameParts(NameMetadata(None, raw_explanation=raw)), BUNDLE, "ru") == raw


def test_name_metadata_accepts_raw_explanation_without_trace_name() -> None:
    metadata = NameMetadata.from_metadata(Metadata.from_dict({"raw_explanation": "${X}", "locale_pronoun": "it"}))

    assert metadata == NameMetadata(None, pronoun="it", raw_explanation="${X}")
    assert NameMetadata.from_metadata(Metadata.from_dict({"locale_pronoun": "it"})) is None


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
def trace_registry() -> SituationRegistry:
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
    return code_snippet_to_registry(code)


@pytest.fixture(scope="module")
def trace_loqi(trace_registry: SituationRegistry) -> str:
    _, loqi = registry_to_loqi(trace_registry)
    return loqi


@pytest.fixture(scope="module")
def lines(trace_registry: SituationRegistry) -> dict[str, int]:
    """Номера строк в коде, сгенерированном Meaning Tree (его и видит студент)."""
    rendered = trace_registry.code.code.splitlines()
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


@pytest.mark.parametrize(
    ("object_id", "en", "ru", "pronoun"),
    [
        ("while_structure_action_BEGIN_ast54", "begin of loop", "начало цикла", "it"),
        ("while_structure_action_END_ast54", "end of loop", "конец цикла", "he"),
    ],
)
def test_boundary_action_names_construct_with_same_ast_id(
    trace_loqi: str, lines: dict[str, int], object_id: str, en: str, ru: str, pronoun: str
) -> None:
    metadata = _object_metadata(trace_loqi, object_id)

    assert metadata == {
        "EN.localizedName": f"{en} <code>while</code> on line {lines['while']}",
        "RU.localizedName": f"{ru} <code>while</code> на строке {lines['while']}",
        "pronoun": pronoun,
    }


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


def test_action_without_rule_metadata_gets_default_statement_name(trace_loqi: str) -> None:
    metadata = _object_metadata(trace_loqi, "block_structure_action_first_ast31")  # i += 1

    assert metadata["EN.localizedName"].startswith("statement on line ")
    assert metadata["pronoun"] == "it"


def test_every_action_and_construct_gets_localized_name(trace_loqi: str) -> None:
    object_ids = re.findall(r"^obj (\S+) : (?:ConcreteAction|ConcreteConstruct) ", trace_loqi, re.MULTILINE)

    assert object_ids
    assert [object_id for object_id in object_ids if "RU.localizedName" not in _object_metadata(trace_loqi, object_id)] == []


def test_trace_act_wraps_action_name_with_traced_affixes(trace_loqi: str) -> None:
    action_metadata = _object_metadata(trace_loqi, "global_statements_structure_action_BEGIN_ast69")
    metadata = _object_metadata(trace_loqi, "act_root")

    assert metadata == {
        "EN.localizedName": f"traced {action_metadata['EN.localizedName']}",
        "RU.localizedName": f"{action_metadata['RU.localizedName']} в трассе",
        "pronoun": action_metadata["pronoun"],
    }


def test_action_spec_gets_name_from_own_metadata_without_line(trace_loqi: str) -> None:
    metadata = _object_metadata(trace_loqi, "action_cond")

    assert metadata == {
        "locale_trace_name": "condition",
        "locale_pronoun": "it",
        "EN.localizedName": "condition",
        "RU.localizedName": "условие",
        "pronoun": "it",
    }
    assert "localizedName" not in str(_object_metadata(trace_loqi, "action_body"))


def test_boundary_action_spec_without_own_metadata_uses_construct_spec(trace_loqi: str) -> None:
    spec_id = re.search(
        r"^obj while_structure_action_BEGIN_ast54 : .*?derivedFrom\((\w+)\)", trace_loqi, re.MULTILINE | re.DOTALL
    )
    assert spec_id is not None

    assert _object_metadata(trace_loqi, spec_id[1]) == {
        "EN.localizedName": "begin of loop <code>while</code>",
        "RU.localizedName": "начало цикла <code>while</code>",
        "pronoun": "it",
    }


def test_semantic_value_name_copies_hint_for_every_language(trace_loqi: str) -> None:
    metadata = _object_metadata(trace_loqi, "semantic_value_action_28_cond_2")

    assert metadata == {"hint": "False", "EN.localizedName": "False", "RU.localizedName": "False"}


def _definition_keys(bundle: MessageBundle, lang: str) -> set[str]:
    return set(bundle._messages[lang])  # pyright: ignore[reportPrivateUsage]
