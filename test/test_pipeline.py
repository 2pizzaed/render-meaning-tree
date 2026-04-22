from unittest.mock import Mock

import pytest

from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    Pipeline,
    PipelineRegistry,
    pipeline_stage,
)


class ListRegistry(PipelineRegistry):
    def __init__(self):
        self.items: list[str] = []

    def collect(self) -> list[str]:
        return self.items.copy()


class RecordingPipeline(Pipeline):
    def __init__(self, *, fork_allowed: bool = True):
        super().__init__()
        self.registry = ListRegistry()
        self.fork_allowed = fork_allowed

    @property
    def current_result(self) -> PipelineRegistry:
        return self.registry

    def can_fork(self) -> bool:
        return self.fork_allowed and self.current_stage >= 2

    def _fork(self):
        child = type(self)(fork_allowed=self.fork_allowed)
        child.registry.items = self.registry.items.copy()
        return child

    @pipeline_stage(20)
    def second_stage(self):
        self.registry.items.append("second")

    @pipeline_stage(10)
    def first_stage(self):
        self.registry.items.append("first")

    @pipeline_stage(30)
    def third_stage(self):
        self.registry.items.append("third")


class OverriddenRecordingPipeline(RecordingPipeline):
    @pipeline_stage(10)
    def first_stage(self):
        self.registry.items.append("override")


def test_process_runs_stages_by_explicit_stage_number():
    pipeline = RecordingPipeline()

    pipeline.process()

    assert pipeline.current_result.collect() == ["first", "second", "third"]
    assert pipeline.current_stage == 30


def test_subclass_stage_override_replaces_base_stage():
    pipeline = OverriddenRecordingPipeline()

    pipeline.process()

    assert pipeline.current_result.collect() == ["override", "second", "third"]


def test_fork_uses_can_fork():
    pipeline = RecordingPipeline()

    assert not pipeline.can_fork()
    with pytest.raises(RuntimeError, match="Fork is forbidden"):
        pipeline.fork()

    pipeline.process()

    child = pipeline.fork()

    assert isinstance(child, RecordingPipeline)
    assert child.current_result.collect() == ["first", "second", "third"]


def test_domain_pipeline_can_disable_fork_with_flag():
    manager = Mock(language="python")
    pipeline = DomainDataGeneratorPipeline(manager, fork_enabled=False)

    assert not pipeline.can_fork()
    with pytest.raises(RuntimeError, match="Fork is forbidden"):
        pipeline.fork()
