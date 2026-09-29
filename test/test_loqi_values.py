from __future__ import annotations

from src.helpers.tpg.loqi_values import (
    EnumLiteral,
    LoqiPropertyResolver,
    parse_enum_localized_names,
    parse_object_properties,
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
	note = "a \\"quoted\\" text" ;
} [
	RU.localizedName = "действие" ;
]
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


def test_resolver_gives_enum_localized_name_with_fallback_to_value() -> None:
    resolve = LoqiPropertyResolver(SITUATION, DOMAIN)

    assert resolve("trace_state", "interruption_mode", "RU") == "прерывание цикла"
    assert resolve("trace_state", "interruption_mode", "en") == "break"
    assert resolve("effect_x", "interruption_start", "EN") == "none"
    assert resolve("effect_x", "call_stack", "RU") == "none"
    assert resolve("act_1", "note", "RU") == 'a "quoted" text'
    assert resolve("trace_state", "missing", "RU") is None
    assert resolve("missing", "interruption_mode", "RU") is None
