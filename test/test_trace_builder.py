import unittest

from src.cfg.abstractions import (
    ActionSpec,
    AppearanceType,
    Constraints,
    KindChain,
    OptionalBoolValue,
)
from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.cfg import CFG, Metadata, NodeKind
from src.cfg.trace_builder import TraceScenarioConfig, generate_trace_variants


def _make_metadata(kind: str, ast_id: int) -> Metadata:
    return Metadata(
        abstract_action=ActionSpec(role=f"role_{ast_id}", kind=KindChain(kind)),
        wrapped_ast=ASTNodeWrapper(ast_node={"id": ast_id}),
    )


class TraceBuilderTests(unittest.TestCase):
    def setUp(self):
        self.cfg = CFG("trace_test")

        self.condition_node = self.cfg.add_node(
            NodeKind.ATOM,
            role="cond",
            metadata=_make_metadata("condition", 1),
        )
        self.condition_node.appearance = AppearanceType.MANDATORY

        self.body_node = self.cfg.add_node(
            NodeKind.ATOM,
            role="body",
            metadata=_make_metadata("block", 2),
        )
        self.body_node.appearance = AppearanceType.MANDATORY

        # Graph structure: begin -> condition -> (true) body -> condition, (false) end
        self.cfg.connect(self.cfg.begin_node, self.condition_node)
        self.cfg.connect(
            self.condition_node,
            self.body_node,
            constraints=Constraints(condition_value=OptionalBoolValue.true),
        )
        self.cfg.connect(
            self.condition_node,
            self.cfg.end_node,
            constraints=Constraints(condition_value=OptionalBoolValue.false),
        )
        self.cfg.connect(self.body_node, self.condition_node)

    def test_trace_uses_configured_condition_sequence(self):
        scenario = TraceScenarioConfig(
            name="deterministic",
            condition_sequences={1: [True, False]},  # bool значения будут преобразованы в OptionalBoolValue внутри
            max_visits_per_node=3,
        )
        results = generate_trace_variants(self.cfg, [scenario])
        trace = results[0].trace_acts
        condition_values = [act.condition_value for act in trace if act.cfg_node.is_condition()]
        self.assertEqual(condition_values, [OptionalBoolValue.true, OptionalBoolValue.false])

    def test_trace_flips_condition_when_visit_limit_near(self):
        scenario = TraceScenarioConfig(
            name="loop-limit",
            condition_sequences={1: [True, True]},  # bool значения будут преобразованы в OptionalBoolValue внутри
            max_visits_per_node=3,
        )
        results = generate_trace_variants(self.cfg, [scenario])
        trace = results[0].trace_acts
        condition_values = [act.condition_value for act in trace if act.cfg_node.is_condition()]
        # Second visit should flip to False to exit the loop before exceeding the limit
        self.assertEqual(condition_values[-2:], [OptionalBoolValue.true, OptionalBoolValue.false])
        self.assertFalse(results[0].terminated_by_limit)


if __name__ == "__main__":
    unittest.main()

