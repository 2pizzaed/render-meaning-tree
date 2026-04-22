from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from importlib.resources import as_file, files
from typing import Any, Protocol, Self, TypeVar

from src.ast_managers import CodeManager
from src.model.rules import load_construct_declarations
from src.model.situation import Action, Construct


class PipelineRegistry(Protocol):
    def collect(self) -> list[Any]:
        ...


PipelineT = TypeVar("PipelineT", bound="Pipeline")


def pipeline_stage(stage_num: int) -> \
    Callable[[Callable[[PipelineT], None]], Callable[[PipelineT], None]]:
    def decorator(method: Callable[[PipelineT], None]) -> Callable[[PipelineT], None]:
        method.__pipeline_stage__ = stage_num # type: ignore
        return method

    return decorator


class Pipeline(ABC):
    def __init__(self):
        self.stage_num = 0
        self.children: list[Self] = []

    def process(self):
        for stage_num, stage in self._iter_stages():
            self.stage_num = stage_num
            stage(self)

    @property
    def current_stage(self) -> int:
        return self.stage_num

    def fork(self) -> Self:
        if not self.can_fork():
            raise RuntimeError("Fork is forbidden for this pipeline")

        child = self._fork()
        self.children.append(child)
        return child

    def can_fork(self) -> bool:
        return True

    @property
    @abstractmethod
    def current_result(self) -> PipelineRegistry:
        ...

    def flatten_results(self) -> list[PipelineRegistry]:
        result = [self.current_result]
        for child in self.children:
            result.extend(child.flatten_results())
        return result

    @abstractmethod
    def _fork(self) -> Self:
        ...

    @classmethod
    def _iter_stages(cls) -> list[tuple[int, Callable[[Self], None]]]:
        stages: dict[str, tuple[int, Callable[[Self], None]]] = {}
        for base in reversed(cls.__mro__):
            for name, member in base.__dict__.items():
                stage_num: int | None = getattr(member, "__pipeline_stage__", None)
                if callable(member) and stage_num is not None:
                    stages[name] = (stage_num, member) # type: ignore
        return sorted(stages.values(), key=lambda item: item[0])


class SituationDomainDataRegistry:
    def __init__(self, owner: DomainDataGeneratorPipeline):
        self.owner = owner
        self.constructs: dict[int, Construct] = {}
        self.actions: dict[int, list[Action]] = {}
        self.utilities = set()

    def collect(self) -> list[Any]:
        return [*self.constructs.values(),
                *[action for actions in self.actions.values() for action in actions],
                *self.utilities]

    def copy(self, owner: DomainDataGeneratorPipeline) -> SituationDomainDataRegistry:
        new_registry = SituationDomainDataRegistry(owner)
        new_registry.constructs = self.constructs.copy()
        new_registry.actions = {k: v.copy() for k, v in self.actions.items()}
        new_registry.utilities = self.utilities.copy()
        return new_registry


class DomainDataGeneratorPipeline(Pipeline):
    def __init__(self, manager: CodeManager, *, fork_enabled: bool = True):
        super().__init__()
        self.manager = manager
        self.registry = SituationDomainDataRegistry(self)
        self.fork_enabled = fork_enabled

    @property
    def current_result(self) -> SituationDomainDataRegistry:
        return self.registry

    def can_fork(self) -> bool:
        return self.fork_enabled

    def _fork(self) -> Self:
        child = type(self)(self.manager, fork_enabled=False)
        child.registry = self.registry.copy(child)
        return child

    @pipeline_stage(1)
    def _load_rules(self):
        resource = files("src").joinpath("resources", "constructs.yml")
        with as_file(resource) as resource_path:
            self.rules = load_construct_declarations(resource_path)
        self.rules = [
            construct for construct in self.rules
            if construct.applicable_to_language(self.manager.language)
        ]

    @pipeline_stage(2)
    def _generate_constructs(self):
        pass

    @pipeline_stage(3)
    def _fill_actions(self):
        pass

    @pipeline_stage(4)
    def _generate_bool_values(self):
        pass
