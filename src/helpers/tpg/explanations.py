"""Explanation / skill aggregation over a decision-tree trace.

Port of the aggregation logic in CompPrehension's ``DecisionTreeReasonerBackend``
(``collectExplanationsFromTrace`` / ``collectExplanations`` /
``reduceSimilarExplanations`` / ``extractExplanation``). It consumes the JSON trace
emitted by its_Reasoner (``traceEvent`` -> ``DecisionTreeTrace.toJsonValue``) as
reproduced by :mod:`src.tpg_domain` (``ReasoningResult.trace`` when ``json_trace=True``).

Unlike the Java original, this port carries **no rendered explanation text and no
domain terms**: an :class:`Explanation` is a pure structural node (type, source node
id, skill, muted flag, children). String message building (``TemplatingUtils``,
common-prefix trimming, localized "and N more" hints, ``DomainTermAnnotationProcessor``)
is intentionally dropped. The reduced "N similar" placeholder becomes a
:attr:`ExplanationKind.MORE` marker carrying :attr:`Explanation.similar_skipped`
instead of a formatted string.

Requires the trace's aggregation elements to expose ``aggregationMethod`` (added to
``DecisionTreeTraceJsonSerializer.kt``); without it AND/OR grouping cannot be
distinguished.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.helpers.templating import (
    interpolate,
    modifiers_for_language,
    referenced_variables,
    split_reference,
)
from src.tpg_domain import ReasoningResult, variable_localized_name

MAX_SIMILAR_EXPLANATION_COUNT = 3

_AGGREGATION_NODE_TYPES = frozenset({"BranchAggregationNode", "CycleAggregationNode"})


class ExplanationType(Enum):
    """Mirror of ``Explanation.Type``."""

    HINT = "HINT"
    ERROR = "ERROR"


class ExplanationKind(Enum):
    """Distinguishes the message-free stand-ins for the Java ``Explanation`` roles.

    ``LEAF`` — a single explanation extracted from a ``BranchResultNode``;
    ``GROUP`` — an aggregation container (the Java parent with an empty/``":"`` message);
    ``MORE`` — the "N similar were folded away" marker (Java's localized hint).
    Only ``GROUP`` nodes can be *empty* (and thus filtered), matching the Java rule
    that a leaf/marker always carries a non-empty message.
    """

    LEAF = "leaf"
    GROUP = "group"
    MORE = "more"


class _AggregationPolicy(Enum):
    """Mirror of ``DecisionTreeReasonerBackend.AggregationPolicy``."""

    SIM_AND = "SimAND"
    SIM_OR = "SimOR"
    DEFAULT = "Default"


@dataclass
class Explanation:
    """Message-free counterpart of CompPrehension's ``Explanation``.

    Aggregation preserves the tree shape and skill/mute bookkeeping of the Java
    original but drops all rendered text. ``node_id`` records the source
    ``BranchResultNode`` (its ``id`` metadata, often absent) for leaves; ``skill``
    is the Java ``currentDomainLawName``. ``source_element`` keeps a back-reference
    to the raw trace element a leaf was extracted from, so rendering can resolve
    the explanation text (which lives in that element's metadata) even when the
    node carries no ``id`` — it is excluded from equality and :meth:`to_dict`.
    """

    type: ExplanationType
    kind: ExplanationKind = ExplanationKind.GROUP
    node_id: str | None = None
    skill: str | None = None
    muted: bool = False
    similar_skipped: int = 0
    children: list[Explanation] = field(default_factory=list)
    source_element: dict[str, Any] | None = field(default=None, compare=False, repr=False)

    def is_empty(self) -> bool:
        """A ``GROUP`` with no children is empty; leaves and markers never are."""
        if self.kind is not ExplanationKind.GROUP:
            return False
        return not self.children

    def skill_names(self) -> set[str]:
        """Own skill plus every descendant skill (Java ``getDomainLawNames``)."""
        names: set[str] = set()
        if self.skill is not None:
            names.add(self.skill)
        for child in self.children:
            names |= child.skill_names()
        return names

    def remove_all_mute(self) -> None:
        """Recursively clear the muted flag (Java ``removeAllMute``)."""
        self.muted = False
        for child in self.children:
            child.remove_all_mute()

    def to_dict(self) -> dict[str, Any]:
        """A plain-dict view for serialization / inspection."""
        return {
            "type": self.type.value,
            "kind": self.kind.value,
            "nodeId": self.node_id,
            "skill": self.skill,
            "muted": self.muted,
            "similarSkipped": self.similar_skipped,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def aggregate(
        cls,
        explanation_type: ExplanationType,
        explanations: Iterable[Explanation],
    ) -> Explanation:
        """Java ``Explanation.aggregate``: a root ``GROUP`` over ``explanations``.

        Children are de-duplicated like the Java ``LinkedHashSet`` (see
        :meth:`_add_all_unique`).
        """
        result = cls(type=explanation_type, kind=ExplanationKind.GROUP)
        result._add_all_unique(explanations)
        return result

    def _key(self) -> tuple[Any, ...]:
        """Structural identity used for ``LinkedHashSet``-style de-duplication.

        Stands in for Java ``Explanation.equals`` (which keyed on the rendered
        message); ``muted`` is excluded, matching the Java definition. The source
        element's explanation text is folded in so that leaves with distinct text
        stay distinct even when they share a skill and lack an ``id`` (Java
        distinguished them by message).
        """
        return (
            self.kind,
            self.type,
            self.skill,
            self.node_id,
            self.similar_skipped,
            _explanation_signature(self.source_element),
            tuple(child._key() for child in self.children),
        )

    def _add_all_unique(self, items: Iterable[Explanation]) -> None:
        """Append ``items`` to :attr:`children`, skipping structural duplicates.

        Reproduces ``SequencedSet.addAll`` (insertion-ordered, unique) used for
        the Java ``children`` collection.
        """
        seen = {child._key() for child in self.children}
        for item in items:
            key = item._key()
            if key not in seen:
                seen.add(key)
                self.children.append(item)


def is_correct_answer(trace: dict[str, Any]) -> bool:
    """Whether the branch result of ``trace`` is correct (Java ``isCorrectAnswer``)."""
    return str(trace.get("branchResult")) in {"CORRECT", "true", "True"}


def nested_trace_elements(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """Pre-order flatten of every trace element, descending into nested traces.

    Java ``DecisionTreeReasonerBackend.nestedTraceElements``.
    """
    elements: list[dict[str, Any]] = []
    _nested_trace_walk(trace, elements)
    return elements


def collect_skills(trace: dict[str, Any]) -> list[str]:
    """Collect ``skill`` metadata across the whole trace.

    Port of the ``domainSkills`` gathering in ``Interface.interpretJudgeOutput``:
    each unlocalized value is split on ``;``. Order is preserved and duplicates
    are kept, matching ``Collections.addAll``. (This project keys only on
    ``skill``; ``law`` metadata is intentionally ignored.)
    """
    skills: list[str] = []
    for element in nested_trace_elements(trace):
        skills.extend(_split_metadata(element, "skill"))
    return skills


def collect_explanations_from_trace(
    explanation_type: ExplanationType,
    trace: dict[str, Any],
    denied_skills: Iterable[str] = (),
) -> Explanation:
    """Aggregate explanations of ``explanation_type`` into a tree.

    Port of ``DecisionTreeReasonerBackend.collectExplanationsFromTrace`` without
    message formatting: the common-prefix / raw-message steps are dropped, while
    the skill-hoisting, similar-reduction and denied-skill unmuting are kept.
    """
    denied = set(denied_skills)
    result = Explanation.aggregate(
        explanation_type,
        _collect_explanations(
            explanation_type, trace, None, _AggregationPolicy.DEFAULT, denied
        ),
    )
    # Если в ветви все объяснения принадлежат одному навыку, то у всей ветви этот навык.
    if len({frozenset(child.skill_names()) for child in result.children}) == 1:
        result.skill = result.children[0].skill
    _reduce_similar_explanations(result.children, explanation_type)
    skill_names = result.skill_names()
    if skill_names <= denied:
        result.remove_all_mute()
    return result


def collect_explanations_from_result(
    explanation_type: ExplanationType,
    result: ReasoningResult,
    denied_skills: Iterable[str] = (),
) -> Explanation | None:
    """Convenience wrapper reading the JSON trace off a :class:`ReasoningResult`.

    Returns ``None`` unless the reasoner was run with ``json_trace=True`` (only
    then is ``result.trace`` the structured trace dict this port needs).
    """
    if not isinstance(result.trace, dict):
        return None
    return collect_explanations_from_trace(explanation_type, result.trace, denied_skills)


DEFAULT_MORE_LABEL = "…and {count} more similar"


def collect_unique_skills(trace: dict[str, Any]) -> list[str]:
    """Every ``skill`` declared anywhere in the trace, de-duplicated in first-seen order.

    Unlike reading a single node's metadata, this spans the whole trace (via
    :func:`collect_skills`), trimming blanks.
    """
    skills = collect_skills(trace)
    ordered: dict[str, None] = {}
    for skill in skills:
        cleaned = skill.strip()
        if cleaned:
            ordered.setdefault(cleaned, None)
    return list(ordered)


type PropertyResolver = Callable[[str, tuple[str, ...], str | None, str], str | None]
"""Resolves ``(object name, relationships, property, loc code)`` to text for
``${X.prop}`` / ``${X->rel}`` / ``${X->rel.prop}``
(see :class:`~src.helpers.tpg.loqi_values.LoqiPropertyResolver`)."""


@dataclass(frozen=True, slots=True)
class _RenderContext:
    loc_code: str
    more_label: str
    variables: Mapping[str, Any] | None
    properties: PropertyResolver | None


def flatten_explanation_texts(
    tree: Explanation,
    *,
    loc_code: str = "EN",
    more_label: str = DEFAULT_MORE_LABEL,
    variables: Mapping[str, Any] | None = None,
    properties: PropertyResolver | None = None,
) -> list[str]:
    """Flat, display-ready explanation lines from an aggregation ``tree``.

    Walks in aggregation order, skips muted nodes, resolves each leaf's text from
    its :attr:`Explanation.source_element` (in ``loc_code``) and expands ``MORE``
    markers via ``more_label`` (formatted with ``count``). When ``variables`` is
    given (the reasoner's structured ``variable_objects``), each leaf's text is run
    through :func:`~src.helpers.templating.interpolate`, substituting ``$name``
    / ``${name}`` with the variable's localized name for ``loc_code`` and
    paths like ``${name->rel.prop}`` with the value ``properties`` gives (see
    :func:`_leaf_variables`): the leaf's own variable snapshot takes precedence
    over ``variables``. ``[case='р']`` declines the substituted name for ``RU``
    and keeps it unchanged for other localizations.
    """
    lines: list[str] = []
    ctx = _RenderContext(loc_code, more_label, variables, properties)
    _collect_explanation_texts(tree, ctx, lines)
    return lines


def explanation_view(
    tree: Explanation,
    *,
    loc_code: str = "EN",
    more_label: str = DEFAULT_MORE_LABEL,
    variables: Mapping[str, Any] | None = None,
    properties: PropertyResolver | None = None,
) -> dict[str, Any]:
    """Renderable nested dict for an aggregation ``tree``.

    Same shape as :meth:`Explanation.to_dict` but with each leaf's resolved
    ``text`` attached (from its source element, in ``loc_code``) and ``MORE``
    markers pre-rendered into ``text``, so a template can render the grouped
    structure directly. Leaf texts are interpolated as in
    :func:`flatten_explanation_texts`.
    """
    return _explanation_view(tree, _RenderContext(loc_code, more_label, variables, properties))


def _explanation_view(tree: Explanation, ctx: _RenderContext) -> dict[str, Any]:
    return {
        "kind": tree.kind.value,
        "type": tree.type.value,
        "text": _node_text(tree, ctx),
        "skill": tree.skill,
        "muted": tree.muted,
        "similarSkipped": tree.similar_skipped,
        "children": [_explanation_view(child, ctx) for child in tree.children],
    }


def _collect_explanation_texts(
    node: Explanation,
    ctx: _RenderContext,
    out: list[str],
) -> None:
    for child in node.children:
        if child.muted:
            continue
        if child.kind is ExplanationKind.GROUP:
            _collect_explanation_texts(child, ctx, out)
            continue
        text = _node_text(child, ctx)
        if text:
            out.append(text)


def _node_text(node: Explanation, ctx: _RenderContext) -> str | None:
    """Human text for a single explanation node (``None`` for groups).

    Interpolation is disabled when ``ctx.variables`` is ``None``.
    """
    if node.kind is ExplanationKind.MORE:
        return ctx.more_label.format(count=node.similar_skipped)
    if node.kind is ExplanationKind.LEAF:
        text = _element_localized_text(node.source_element, "explanation", ctx.loc_code)
        if text is not None and ctx.variables is not None:
            variables = _leaf_variables(node.source_element, text, ctx)
            return interpolate(text, variables, modifiers_for_language(ctx.loc_code))
        return text
    return None


def _leaf_variables(
    element: dict[str, Any] | None,
    template: str,
    ctx: _RenderContext,
) -> dict[str, str]:
    """Values for interpolating a leaf's ``template``.

    Each trace element carries ``variables`` — the snapshot at the moment its node
    finished. For a ``BranchResultNode`` this is the context of the conclude node
    itself (fragment locals, the current iteration of a cycle aggregation), while
    the reasoner's final variables only hold the last assigned values. The snapshot
    therefore wins; final variables fill in names it lacks.

    A variable becomes its ``localizedName`` for the localization — falling back
    to ``object_name`` then ``repr_name`` — via
    :func:`~src.tpg_domain.variable_localized_name`, matching how its_QuestionGen
    renders ``Obj`` variables in templates. A path reference (``name.prop``,
    ``name->rel.prop``) is resolved by ``ctx.properties`` for the object bound to
    ``name``.
    """
    objects: dict[str, Any] = dict(ctx.variables or {})
    snapshot = element.get("variables") if element is not None else None
    if isinstance(snapshot, dict):
        objects.update({str(name): value for name, value in snapshot.items()})
    values = {
        name: variable_localized_name(value, ctx.loc_code) for name, value in objects.items()
    }
    if ctx.properties is not None:
        for reference in referenced_variables(template):
            name, relationships, prop = split_reference(reference)
            if (relationships or prop) and name in objects:
                value = ctx.properties(
                    _variable_identity(objects[name]), relationships, prop, ctx.loc_code
                )
                if value is not None:
                    values[reference] = value
    return values


type _ExplanationSignature = tuple[
    tuple[tuple[str | None, str], ...],
    tuple[tuple[str, str], ...],
]


def _explanation_signature(element: dict[str, Any] | None) -> _ExplanationSignature:
    """Stable, hashable digest of an element's ``explanation`` localizations.

    Used as the message stand-in in :meth:`Explanation._key` so distinct
    explanation texts do not collapse during de-duplication. Besides the
    templates, it includes the objects bound to the variables they interpolate:
    one conclude node reached with different objects (e.g. on different levels of
    a cycle aggregation) renders distinct messages.
    """
    if element is None:
        return (), ()
    entries = [
        (entry.get("locCode"), str(entry.get("value")))
        for entry in _metadata_entries(element)
        if isinstance(entry, dict)
        and entry.get("name") == "explanation"
        and entry.get("value") is not None
    ]
    templates = tuple(sorted(entries, key=lambda item: (item[0] or "", item[1])))
    snapshot = element.get("variables")
    if not isinstance(snapshot, dict):
        return templates, ()
    names = {
        split_reference(reference)[0]
        for _, text in entries
        for reference in referenced_variables(text)
    }
    bound = tuple(
        sorted(
            (name, _variable_identity(snapshot[name]))
            for name in names
            if name in snapshot
        )
    )
    return templates, bound


def _variable_identity(value: Any) -> str:
    """The object a variable snapshot entry refers to (its name in the situation)."""
    if isinstance(value, dict):
        for key in ("object_name", "repr_name"):
            if value.get(key) is not None:
                return str(value[key])
    return str(value)


def _element_localized_text(
    element: dict[str, Any] | None,
    name: str,
    loc_code: str,
) -> str | None:
    if element is None:
        return None
    grouped: dict[str | None, list[str]] = {}
    for entry in _metadata_entries(element):
        if (
            isinstance(entry, dict)
            and entry.get("name") == name
            and entry.get("value") is not None
        ):
            grouped.setdefault(entry.get("locCode"), []).append(str(entry.get("value")))
    values = (
        grouped.get(loc_code)
        or grouped.get(loc_code.lower())
        or grouped.get(None)
        or [value for entries in grouped.values() for value in entries]
    )
    return values[0] if values else None


def _collect_explanations(
    explanation_type: ExplanationType,
    trace: dict[str, Any],
    parent: Explanation | None,
    policy: _AggregationPolicy,
    denied: set[str],
) -> list[Explanation]:
    """Recursive per-trace explanation collection (Java ``collectExplanations``).

    When ``parent`` is set, collected explanations are folded into it and an empty
    list is returned; otherwise the (non-empty, similarity-reduced) list is returned.
    """
    trace_explanations: list[Explanation] = []
    for element in _trace_elements(trace):
        nested = _nested_traces(element)
        node_type = element.get("nodeType")
        node_result = element.get("nodeResult")
        is_leaf = (
            not nested
            and node_type == "BranchResultNode"
            and (explanation_type is ExplanationType.ERROR) != (node_result == "CORRECT")
            and _metadata_contains(element, "explanation")
        )
        if is_leaf:
            # Одиночное объяснение по заданному типу объяснения.
            explanation = _extract_explanation(element)
            if explanation.skill_names() & denied:
                explanation.muted = True
            trace_explanations.append(explanation)
            continue

        # Элемент трассы может включать другие трассы.
        new_parent = parent
        new_policy = policy
        aggregation_method = element.get("aggregationMethod")
        if node_type in _AGGREGATION_NODE_TYPES and aggregation_method == "AND":
            new_policy = _AggregationPolicy.SIM_AND
            if explanation_type is ExplanationType.HINT and policy is not new_policy:
                # Для Sim:AND и подсказок элементы агрегаций объединяются в новую ветвь.
                new_parent = Explanation(type=explanation_type, kind=ExplanationKind.GROUP)
                trace_explanations.append(new_parent)
        elif node_type in _AGGREGATION_NODE_TYPES and aggregation_method == "OR":
            new_policy = _AggregationPolicy.SIM_OR
            if explanation_type is ExplanationType.ERROR and policy is not new_policy:
                # Для Sim:OR и ошибок элементы агрегаций объединяются в новую ветвь.
                new_parent = Explanation(type=explanation_type, kind=ExplanationKind.GROUP)
                trace_explanations.append(new_parent)

        for sub_trace in nested:
            trace_explanations.extend(
                _collect_explanations(
                    explanation_type, sub_trace, new_parent, new_policy, denied
                )
            )

        # Если в агрегированной ветви один элемент - хранить только его, если нет - удалить ветвь.
        if new_parent is not None and len(new_parent.children) <= 1:
            _remove_identity(trace_explanations, new_parent)
            if len(new_parent.children) == 1:
                trace_explanations.append(new_parent.children[0])

    non_empty = [item for item in trace_explanations if not item.is_empty()]
    if parent is None:
        _reduce_similar_explanations(non_empty, explanation_type)
        return non_empty

    parent._add_all_unique(non_empty)
    _reduce_similar_explanations(parent.children, explanation_type)
    if len({frozenset(child.skill_names()) for child in parent.children}) == 1:
        parent.skill = parent.children[0].skill
    return []


def _reduce_similar_explanations(
    explanations: list[Explanation],
    explanation_type: ExplanationType,
) -> None:
    """Fold away explanations beyond :data:`MAX_SIMILAR_EXPLANATION_COUNT` per skill.

    Java ``reduceSimilarExplanations``: mutates ``explanations`` in place, dropping
    the excess and appending a ``MORE`` marker carrying the dropped count (the Java
    localized "and N more" hint, minus the text). When called repeatedly on a
    growing children collection, Java folds equal markers away because that
    collection is a ``LinkedHashSet``; the marker append here is de-duplicated to
    match — so, like Java, the surviving marker reports the last call's count, not
    the running total.
    """
    skill_counter: dict[str | None, int] = {}
    delete_candidates: list[Explanation] = []
    for item in explanations:
        total = skill_counter.get(item.skill, 0) + 1
        skill_counter[item.skill] = total
        if total > MAX_SIMILAR_EXPLANATION_COUNT and item.skill is not None:
            delete_candidates.append(item)
    if not delete_candidates:
        return
    for candidate in delete_candidates:
        _remove_identity(explanations, candidate)
    marker = Explanation(
        type=explanation_type,
        kind=ExplanationKind.MORE,
        similar_skipped=len(delete_candidates),
    )
    marker_key = marker._key()
    if not any(item._key() == marker_key for item in explanations):
        explanations.append(marker)


def _extract_explanation(element: dict[str, Any]) -> Explanation:
    """Build a leaf explanation from a ``BranchResultNode`` element.

    Port of ``Interface.extractExplanation`` without message interpretation: the
    node's type (by result), source id, ``skill`` and ``muted`` metadata are kept.
    """
    node_result = element.get("nodeResult")
    explanation_type = (
        ExplanationType.HINT if node_result == "CORRECT" else ExplanationType.ERROR
    )
    explanation = Explanation(
        type=explanation_type,
        kind=ExplanationKind.LEAF,
        node_id=_element_node_id(element),
        source_element=element,
    )
    if _metadata_contains(element, "skill"):
        explanation.skill = _metadata_unlocalized(element, "skill")
    muted = _metadata_unlocalized(element, "muted")
    if (
        _metadata_contains(element, "muted")
        and muted is not None
        and muted.strip().lower() == "true"
    ):
        explanation.muted = True
    return explanation


def _nested_trace_walk(trace: dict[str, Any], elements: list[dict[str, Any]]) -> None:
    for element in _trace_elements(trace):
        elements.append(element)
        for sub_trace in _nested_traces(element):
            _nested_trace_walk(sub_trace, elements)


def _trace_elements(trace: dict[str, Any]) -> list[dict[str, Any]]:
    raw = trace.get("elements")
    return [element for element in raw if isinstance(element, dict)] if isinstance(raw, list) else []


def _nested_traces(element: dict[str, Any]) -> list[dict[str, Any]]:
    """The nested branch traces of a trace element (Java ``nestedTraces``).

    Aggregation elements nest one trace per branch/iteration; a redirected
    branch-result element nests its single subinterpreter trace. Everything else
    has no nested traces.
    """
    branches = element.get("branches")
    if isinstance(branches, list):
        return [
            branch["trace"]
            for branch in branches
            if isinstance(branch, dict) and isinstance(branch.get("trace"), dict)
        ]
    iterations = element.get("iterations")
    if isinstance(iterations, list):
        return [
            iteration["trace"]
            for iteration in iterations
            if isinstance(iteration, dict) and isinstance(iteration.get("trace"), dict)
        ]
    redirected = element.get("redirectedTrace")
    if isinstance(redirected, dict):
        return [redirected]
    return []


def _split_metadata(element: dict[str, Any], name: str) -> list[str]:
    if not _metadata_contains(element, name):
        return []
    value = _metadata_unlocalized(element, name)
    return value.split(";") if value is not None else []


def _metadata_contains(element: dict[str, Any], name: str) -> bool:
    """Java ``MetaData.containsAny``: the property exists under any localization."""
    return any(
        isinstance(entry, dict) and entry.get("name") == name
        for entry in _metadata_entries(element)
    )


def _metadata_unlocalized(element: dict[str, Any], name: str) -> str | None:
    """Java ``MetaData.getString(name)``: the unlocalized (``locCode is None``) value."""
    for entry in _metadata_entries(element):
        if (
            isinstance(entry, dict)
            and entry.get("name") == name
            and entry.get("locCode") is None
        ):
            value = entry.get("value")
            return None if value is None else str(value)
    return None


def _metadata_entries(element: dict[str, Any]) -> list[Any]:
    raw = element.get("metadata")
    return raw if isinstance(raw, list) else []


def _element_node_id(element: dict[str, Any]) -> str | None:
    node_id = element.get("nodeId")
    return None if node_id is None else str(node_id)


def _remove_identity(items: list[Explanation], target: Explanation) -> None:
    """Remove the first element that *is* ``target`` (object identity)."""
    for index, item in enumerate(items):
        if item is target:
            del items[index]
            return
