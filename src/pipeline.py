"""Поэтапный pipeline с ветвлением.

Pipeline выполняет по порядку стадии - методы, перечисленные по имени в ``stages``.
Стадия может ответвить работу в дочерний pipeline (``fork_redirect``): он получает
копию registry и проходит свои стадии сразу после завершения текущей стадии родителя. После ветвления pipeline
перестаёт быть результатом сам - результатом становятся его живые листья.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterator
from typing import Any, ClassVar, Self


class PipelineRegistry:
    """Рабочая память pipeline; наследники - изменяемые dataclass-ы."""

    # Поля, общие для всех веток: clone() оставляет на них ссылки, а не копирует.
    shared: ClassVar[tuple[str, ...]] = ()

    def clone(self) -> Self:
        return copy.deepcopy(self, self.shared_memo())

    def shared_memo(self) -> dict[int, Any]:
        """Memo для deepcopy, в котором общие поля уже «скопированы» в самих себя."""
        values = (getattr(self, name) for name in self.shared)
        return {id(value): value for value in values}


class Pipeline[R: PipelineRegistry]:
    # Имена методов-стадий в порядке выполнения.
    stages: ClassVar[tuple[str, ...]] = ()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        unknown = [name for name in cls.stages if not callable(getattr(cls, name, None))]
        if unknown:
            raise TypeError(f"{cls.__name__} declares unknown stages: {unknown}")

    def __init__(self, registry: R) -> None:
        self.registry = registry
        self.forked: list[Pipeline[R]] = []
        self.stage_num = 0
        self._terminated = False

    @property
    def is_terminated(self) -> bool:
        return self._terminated

    @property
    def is_finished(self) -> bool:
        return self._terminated or self.stage_num >= len(self.stages)

    @property
    def current_stage(self) -> str | None:
        if self.is_finished:
            return None
        return self.stages[self.stage_num]

    def execute(self) -> Iterator[tuple[Pipeline[Any], str]]:
        """Выполнять стадии, отдавая (pipeline, имя стадии) после каждой, включая стадии веток."""
        while not self.is_finished:
            stage = self.stages[self.stage_num]
            getattr(self, stage)()
            yield self, stage
            if not self._terminated:
                # Незавершённые ветки - только что созданные этой стадией.
                for child in [child for child in self.forked if not child.is_finished]:
                    yield from child.execute()
            self.stage_num += 1

    def run(self) -> Self:
        for _ in self.execute():
            pass
        return self

    def fork_redirect[P: Pipeline[Any]](self, pipeline_type: Callable[[R], P]) -> P:
        """Создать ветку с копией registry; её стадии выполнятся после текущей стадии."""
        child = pipeline_type(self.registry.clone())
        self.forked.append(child)
        return child

    def terminate(self) -> None:
        """Пометить pipeline неудачным: он и его ветки исключаются из результатов."""
        self._terminated = True

    def reduce(self, predicate: Callable[[Pipeline[Any]], bool]) -> None:
        """Отбросить листья веток, не прошедшие predicate, и убрать terminated ветки.

        Ветка, у которой не осталось живых потомков, тоже отбрасывается.
        """
        for child in self.forked:
            for leaf in child.leaves():
                if not predicate(leaf):
                    leaf.terminate()
        self._prune_terminated()

    def leaves(self) -> list[Pipeline[Any]]:
        if self._terminated:
            return []
        if not self.forked:
            return [self]
        return [leaf for child in self.forked for leaf in child.leaves()]

    def collect(self) -> Any:
        """Результат листа; по умолчанию - его registry."""
        return self.registry

    def results(self) -> list[Any]:
        return [leaf.collect() for leaf in self.leaves()]

    def _prune_terminated(self) -> None:
        if not self.forked:
            return
        for child in self.forked:
            child._prune_terminated()
        self.forked = [child for child in self.forked if not child.is_terminated]
        if not self.forked:
            self.terminate()
