from __future__ import annotations

from typing import Any

from src.helpers.tpg.explanations import (
    ExplanationType,
    collect_explanations_from_trace,
    flatten_explanation_texts,
)
from src.helpers.tpg.templating import (
    interpolate,
    referenced_variables,
    split_reference,
)

NAMES = {"A": "условие на строке 2", "C": "цикл <code>while</code>"}


def test_case_modifier_keeps_nominative_in_both_syntaxes() -> None:
    assert (
        interpolate("к ${A}[case='д'] внутри ${C}[case('р')]", NAMES)
        == "к условие на строке 2 внутри цикл <code>while</code>"
    )


def test_modifier_list_is_applied_left_to_right() -> None:
    modifiers = {"wrap": lambda text, left, right: f"{left}{text}{right}", "upper": str.upper}

    assert interpolate("${A}[upper, wrap('«', \"»\"),]", {"A": "x"}, modifiers) == "«X»"


def test_unknown_modifier_or_variable_stays_verbatim() -> None:
    template = "${A}[declension='р'] и ${B}[case='р']"

    assert interpolate(template, NAMES) == template


def test_brackets_are_modifiers_only_right_after_braced_interpolation() -> None:
    assert interpolate("$A[case='р']", NAMES) == "условие на строке 2[case='р']"
    assert interpolate("${A} [case='р']", NAMES) == "условие на строке 2 [case='р']"


def test_non_modifier_brackets_stay_text_and_are_interpolated() -> None:
    assert interpolate("${A}[1] и ${A}[про $C]", NAMES) == (
        "условие на строке 2[1] и условие на строке 2[про цикл <code>while</code>]"
    )


def test_referenced_variables_ignores_expressions_and_escapes() -> None:
    template = "${A}[case='р'] $C ${3+3} \\$D ${S.mode} ${S->rel} ${f(S).mode} ${S.a.b} ${S.mode->rel}"

    assert referenced_variables(template) == {"A", "C", "S.mode", "S->rel"}


def test_relationship_path_is_split_into_parts() -> None:
    assert split_reference("A") == ("A", (), None)
    assert split_reference("S.mode") == ("S", (), "mode")
    assert split_reference("D->hasValue->next.bool_value") == ("D", ("hasValue", "next"), "bool_value")


def test_property_reference_is_looked_up_by_its_path() -> None:
    values = {"S": "состояние", "S.mode": "возврат из функции"}

    assert interpolate("идёт ${S.mode}[case='р'], $S.mode", values) == "идёт возврат из функции, состояние.mode"


def _obj(object_name: str, ru_name: str) -> dict[str, Any]:
    return {
        "repr_name": object_name,
        "object_name": object_name,
        "type": "ConcreteConstruct",
        "metadata": [{"name": "localizedName", "locCode": "RU", "value": ru_name}],
    }


def _conclude(variables: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodeType": "BranchResultNode",
        "nodeResult": "ERROR",
        "variables": variables,
        "metadata": [
            {"name": "skill", "locCode": None, "value": "construct_not_closed"},
            {"name": "explanation", "locCode": "RU", "value": "Выполнение ${C}[case='р'] не завершено."},
        ],
    }


def test_leaf_text_uses_its_own_variable_snapshot() -> None:
    """Один conclude-узел на двух итерациях цикла агрегации — два разных объекта C."""
    levels = [_obj("construct_if", "ветвление"), _obj("construct_block", "блок кода")]
    trace = {
        "branchResult": "ERROR",
        "elements": [
            {
                "nodeType": "CycleAggregationNode",
                "aggregationMethod": "AND",
                "nodeResult": "ERROR",
                "variables": {},
                "metadata": [],
                "branches": [
                    {"branch": str(index), "trace": {"elements": [_conclude({"C": level})]}}
                    for index, level in enumerate(levels)
                ],
            }
        ],
    }

    tree = collect_explanations_from_trace(ExplanationType.ERROR, trace)
    # Финальные переменные рассуждателя содержат только последнее значение C.
    texts = flatten_explanation_texts(tree, loc_code="RU", variables={"C": levels[-1]})

    assert texts == ["Выполнение ветвление не завершено.", "Выполнение блок кода не завершено."]


def test_property_of_snapshot_variable_is_resolved_for_its_object() -> None:
    conclude = _conclude({"S": _obj("trace_state", "состояние")})
    conclude["metadata"][1]["value"] = "Идёт ${S.interruption_mode}."
    trace = {"branchResult": "ERROR", "elements": [conclude]}
    tree = collect_explanations_from_trace(ExplanationType.ERROR, trace)
    calls: list[tuple[str, str, str]] = []

    def properties(
        object_name: str, relationships: tuple[str, ...], prop: str | None, loc_code: str
    ) -> str | None:
        assert relationships == ()
        assert prop is not None
        calls.append((object_name, prop, loc_code))
        return "возврат из функции"

    assert flatten_explanation_texts(tree, loc_code="RU", variables={}, properties=properties) == [
        "Идёт возврат из функции."
    ]
    assert calls == [("trace_state", "interruption_mode", "RU")]
    # без resolver свойство не разрешается и остаётся в тексте как есть
    assert flatten_explanation_texts(tree, loc_code="RU", variables={}) == ["Идёт ${S.interruption_mode}."]


def test_relationship_path_of_snapshot_variable_is_resolved_for_its_object() -> None:
    conclude = _conclude({"D": _obj("act_7", "акт")})
    conclude["metadata"][1]["value"] = "Значение ${D->hasValue.bool_value}, ${D->hasValue}."
    trace = {"branchResult": "ERROR", "elements": [conclude]}
    tree = collect_explanations_from_trace(ExplanationType.ERROR, trace)
    calls: list[tuple[str, tuple[str, ...], str | None]] = []

    def properties(
        object_name: str, relationships: tuple[str, ...], prop: str | None, loc_code: str
    ) -> str | None:
        calls.append((object_name, relationships, prop))
        return "true" if prop == "bool_value" else None

    assert flatten_explanation_texts(tree, loc_code="RU", variables={}, properties=properties) == [
        "Значение true, ${D->hasValue}."
    ]
    assert sorted(calls, key=str) == [("act_7", ("hasValue",), "bool_value"), ("act_7", ("hasValue",), None)]
