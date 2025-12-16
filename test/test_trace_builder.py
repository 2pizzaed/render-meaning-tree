import unittest

from src.cfg.abstractions import (
    ActionSpec,
    AppearanceType,
    CallStackAction,
    Constraints,
    Effects,
    InterruptionType,
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

    def test_function_end_prefers_edge_matching_call_stack_top(self):
        """Проверяет, что _choose_next_node выбирает ребро с DROP_FRAME,
        ведущее к обёртке вызова с ast_id, совпадающим с вершиной стека."""

        from src.cfg.trace_builder import _ConditionDecisionProvider, _choose_next_node

        cfg = CFG("call_stack_edge_choice")

        # Общий конец функции
        FUNC_AST_ID = 200
        CALL1_AST_ID = 101
        CALL2_AST_ID = 102

        func_end = cfg.add_node(NodeKind.END, role="func_body_end", metadata=_make_metadata("block", FUNC_AST_ID))
        call1_end = cfg.add_node(NodeKind.END, role="call1_end", metadata=_make_metadata("inline", CALL1_AST_ID))
        call2_end = cfg.add_node(NodeKind.END, role="call2_end", metadata=_make_metadata("inline", CALL2_AST_ID))

        # Делаем узлы обязательными, чтобы они были допустимыми целями
        for n in (func_end, call1_end, call2_end):
            n.appearance = AppearanceType.MANDATORY

        drop_frame_effect = Effects(call_stack=CallStackAction.DROP_FRAME)

        # Два ребра возврата с DROP_FRAME к разным обёрткам вызовов
        e1 = cfg.connect(func_end, call1_end)
        e1.effects.append(drop_frame_effect)
        e2 = cfg.connect(func_end, call2_end)
        e2.effects.append(drop_frame_effect)

        scenario = TraceScenarioConfig(name="call_stack_choice", randomize_missing_conditions=False)
        provider = _ConditionDecisionProvider(cfg, scenario)

        # Если на вершине стека CALL2_AST_ID, должно быть выбрано ребро к call2_end
        next_node, cond_val, chosen_edge = _choose_next_node(
            cfg,
            func_end,
            visit_count=1,
            scenario=scenario,
            provider=provider,
            interruption_state=InterruptionType.NO_INTERRUPTION,
            current_call_ast_id=CALL2_AST_ID,
        )
        self.assertIsNotNone(next_node)
        self.assertEqual(next_node.metadata.wrapped_ast.ast_node.get("id"), CALL2_AST_ID)

        # Если на вершине стека CALL1_AST_ID, должно быть выбрано ребро к call1_end
        next_node, cond_val, chosen_edge = _choose_next_node(
            cfg,
            func_end,
            visit_count=1,
            scenario=scenario,
            provider=provider,
            interruption_state=InterruptionType.NO_INTERRUPTION,
            current_call_ast_id=CALL1_AST_ID,
        )
        self.assertIsNotNone(next_node)
        self.assertEqual(next_node.metadata.wrapped_ast.ast_node.get("id"), CALL1_AST_ID)


if __name__ == "__main__":
    unittest.main()

