from __future__ import annotations

from src.helpers.tpg.loqi_values import (
    EnumLiteral,
    LoqiPropertyResolver,
    parse_enum_localized_names,
    parse_object_properties,
    parse_objects,
)

DOMAIN = """
enum InterruptionType {
    // комментарий с "кавычками" и [скобками]
    break [
        RU.localizedName = "прерывание цикла" ;
        EN.localizedName = "break" ;
    ],
    none [
        RU.localizedName = "обычное выполнение" ;
    ],
} [
    RU.localizedName = "тип прерывания" ;
]

enum OptionalBool { `true`, `null` }
"""

SITUATION = """
obj trace_state : TraceState {
	interruption_mode = InterruptionType:break ;

}

obj effect_x : Effect {
	interruption_start = InterruptionType:none ;
	call_stack = CallStackAction:none ;
}

obj act_1 : TraceAct {
	hasAction(action_1);
	hasValue(value_1);
	directlyBeforeOf(act_2);
	directlyBeforeOf(act_3);
	isBetween(act_2, act_3);
	note = "a \\"quoted\\" text" ;
} [
	RU.localizedName = "действие" ;
]

obj action_1 : ConcreteAction {
	hasValue(value_1);
} [
	RU.localizedName = "условие \\"x\\" [на строке 2]" ;
	EN.localizedName = "condition" ;
]

obj value_1 : SemanticValue {
	bool_value = true;
}
"""


def test_parse_enum_localized_names_skips_comments_and_backticks() -> None:
    assert parse_enum_localized_names(DOMAIN) == {
        "InterruptionType": {
            "break": {"RU": "прерывание цикла", "EN": "break"},
            "none": {"RU": "обычное выполнение"},
        },
        "OptionalBool": {"true": {}, "null": {}},
    }


def test_parse_object_properties_reads_scalars_but_not_relationships() -> None:
    objects = parse_object_properties(SITUATION)

    assert objects["trace_state"] == {"interruption_mode": EnumLiteral("InterruptionType", "break")}
    assert objects["act_1"] == {"note": 'a "quoted" text'}


def test_parse_objects_reads_one_target_links_and_localized_names() -> None:
    objects = parse_objects(SITUATION)

    assert objects["act_1"].relationships == {
        "hasAction": ["action_1"],
        "hasValue": ["value_1"],
        "directlyBeforeOf": ["act_2", "act_3"],
    }
    assert objects["act_1"].localized_names == {"RU": "действие"}
    assert objects["action_1"].localized_names == {"RU": 'условие "x" [на строке 2]', "EN": "condition"}
    assert objects["trace_state"].localized_names == {}


def test_resolver_gives_enum_localized_name_with_fallback_to_value() -> None:
    resolve = LoqiPropertyResolver(SITUATION, DOMAIN)

    assert resolve("trace_state", (), "interruption_mode", "RU") == "прерывание цикла"
    assert resolve("trace_state", (), "interruption_mode", "en") == "break"
    assert resolve("effect_x", (), "interruption_start", "EN") == "none"
    assert resolve("effect_x", (), "call_stack", "RU") == "none"
    assert resolve("act_1", (), "note", "RU") == 'a "quoted" text'
    assert resolve("trace_state", (), "missing", "RU") is None
    assert resolve("missing", (), "interruption_mode", "RU") is None


def test_resolver_follows_relationships() -> None:
    resolve = LoqiPropertyResolver(SITUATION, DOMAIN)

    assert resolve("act_1", ("hasValue",), "bool_value", "RU") == "true"
    assert resolve("act_1", ("hasAction", "hasValue"), "bool_value", "RU") == "true"
    # без свойства — localizedName достигнутого объекта
    assert resolve("act_1", ("hasAction",), None, "en") == "condition"
    assert resolve("act_1", ("hasValue",), None, "RU") is None
    # нет связи, неоднозначная связь, n-арная связь, связь с неизвестным объектом
    assert resolve("act_1", ("missing",), "bool_value", "RU") is None
    assert resolve("act_1", ("directlyBeforeOf",), None, "RU") is None
    assert resolve("act_1", ("isBetween",), None, "RU") is None
    assert resolve("action_1", ("hasValue", "hasValue"), "bool_value", "RU") is None
