from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

import pytest

from src.pipeline import Pipeline, PipelineRegistry


@dataclass
class ListRegistry(PipelineRegistry):
    shared: ClassVar[tuple[str, ...]] = ("config",)

    items: list[str] = field(default_factory=list)
    config: dict[str, str] = field(default_factory=dict)


class BranchPipeline(Pipeline[ListRegistry]):
    stages = ("mark",)

    def mark(self) -> None:
        self.registry.items.append("branch")


class ForkingPipeline(Pipeline[ListRegistry]):
    stages = ("first", "fork_twice", "last")

    def first(self) -> None:
        self.registry.items.append("first")

    def fork_twice(self) -> None:
        self.registry.items.append("fork")
        self.fork_redirect(BranchPipeline).registry.items.append("a")
        self.fork_redirect(BranchPipeline).registry.items.append("b")

    def last(self) -> None:
        self.registry.items.append("last")


class NestedPipeline(Pipeline[ListRegistry]):
    """Ветка, которая сама ветвится на два листа."""

    stages = ("fork_leaves",)

    def fork_leaves(self) -> None:
        for name in ("x", "y"):
            self.fork_redirect(BranchPipeline).registry.items.append(name)


class RootPipeline(Pipeline[ListRegistry]):
    stages = ("fork_nested",)

    def fork_nested(self) -> None:
        for name in ("a", "b"):
            self.fork_redirect(NestedPipeline).registry.items.append(name)


def _items(pipeline: Pipeline[ListRegistry]) -> list[list[str]]:
    return [registry.items for registry in pipeline.results()]


def test_execute_runs_branch_stages_right_after_forking_stage():
    pipeline = ForkingPipeline(ListRegistry())

    steps = [(type(step).__name__, stage) for step, stage in pipeline.execute()]

    assert steps == [
        ("ForkingPipeline", "first"),
        ("ForkingPipeline", "fork_twice"),
        ("BranchPipeline", "mark"),
        ("BranchPipeline", "mark"),
        ("ForkingPipeline", "last"),
    ]
    assert pipeline.is_finished
    assert pipeline.current_stage is None
    assert pipeline.stage_num == len(pipeline.stages)


def test_results_are_leaves_with_their_own_registry_copies():
    pipeline = ForkingPipeline(ListRegistry()).run()

    assert _items(pipeline) == [
        ["first", "fork", "a", "branch"],
        ["first", "fork", "b", "branch"],
    ]
    assert pipeline.registry.items == ["first", "fork", "last"]


def test_pipeline_without_forks_is_its_own_result():
    pipeline = BranchPipeline(ListRegistry()).run()

    assert pipeline.results() == [pipeline.registry]


def test_clone_copies_registry_but_keeps_shared_fields():
    registry = ListRegistry(items=["item"], config={"key": "value"})

    clone = registry.clone()
    clone.items.append("changed")

    assert registry.items == ["item"]
    assert clone.config is registry.config


def test_terminated_branch_is_excluded_from_results():
    pipeline = ForkingPipeline(ListRegistry()).run()

    pipeline.forked[0].terminate()

    assert _items(pipeline) == [["first", "fork", "b", "branch"]]


def test_terminate_inside_stage_stops_remaining_stages():
    class StoppingPipeline(Pipeline[ListRegistry]):
        stages = ("stop", "unreachable")

        def stop(self) -> None:
            self.terminate()

        def unreachable(self) -> None:
            self.registry.items.append("unreachable")

    pipeline = StoppingPipeline(ListRegistry()).run()

    assert pipeline.is_terminated
    assert pipeline.registry.items == []
    assert pipeline.results() == []


def test_reduce_filters_nested_leaves_and_prunes_empty_branches():
    pipeline = RootPipeline(ListRegistry()).run()
    assert _items(pipeline) == [
        ["a", "x", "branch"],
        ["a", "y", "branch"],
        ["b", "x", "branch"],
        ["b", "y", "branch"],
    ]

    pipeline.reduce(lambda leaf: leaf.registry.items[0] == "a" or "y" in leaf.registry.items)

    assert _items(pipeline) == [
        ["a", "x", "branch"],
        ["a", "y", "branch"],
        ["b", "y", "branch"],
    ]

    pipeline.reduce(lambda leaf: leaf.registry.items[0] == "a")

    assert [branch.registry.items for branch in pipeline.forked] == [["a"]]
    assert _items(pipeline) == [["a", "x", "branch"], ["a", "y", "branch"]]


def test_unknown_stage_name_is_rejected_at_class_definition():
    with pytest.raises(TypeError, match="unknown stages"):

        class _TypoPipeline(Pipeline[ListRegistry]):
            stages = ("missing",)


def test_reduce_rejecting_all_leaves_terminates_pipeline():
    pipeline = RootPipeline(ListRegistry()).run()

    pipeline.reduce(lambda leaf: False)

    assert pipeline.forked == []
    assert pipeline.is_terminated
    assert pipeline.results() == []
