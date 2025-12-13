# Define dataclasses matching the constructs structure

import os
import sys
from dataclasses import dataclass, field
from typing import Optional, Self

import yaml

import src.cfg.ast_wrapper as aw
from src.common_utils import DictLikeDataclass, SelfValidatedEnum

BEGIN = 'BEGIN'
END = 'END'


class OriginType(SelfValidatedEnum):
    """Origin types for identification"""
    PARENT = "parent"
    PREVIOUS = "previous"


class RoleInListType(SelfValidatedEnum):
    """Role in list types for identification"""
    FIRST_IN_LIST = "first_in_list"
    NEXT_IN_LIST = "next_in_list"


class InterruptionType(SelfValidatedEnum):
    """Interruption types for constraints & effects"""
    NO_INTERRUPTION = "no_interruption"
    GENERIC_INTERRUPTION = "generic_interruption"  # присутствует прерывание любого вида (break, continue, return, exception).
    BREAK = "break"
    CONTINUE = "continue"
    RETURN = "return"
    EXCEPTION = "exception"
    ANY = "any"  # Прерывание может быть, а может и не быть: и то и то разрешено.
    DEFAULT = NO_INTERRUPTION  # alias

    @classmethod
    def _get_specific_types(cls) -> set['InterruptionType']:
        """Конкретные типы прерываний (без GENERIC_INTERRUPTION, NO_INTERRUPTION, ANY)"""
        return {cls.BREAK, cls.CONTINUE, cls.RETURN, cls.EXCEPTION}

    def fits(self, other: 'InterruptionType | None') -> bool:
        """Проверяет, покрывает ли текущий тип прерывания запрошенный.
        
        Логика:
        - ANY покрывает всё (кроме None)
        - GENERIC_INTERRUPTION покрывает все конкретные типы (BREAK, CONTINUE, RETURN, EXCEPTION)
        - Конкретный тип покрывает только себя
        - NO_INTERRUPTION покрывает только NO_INTERRUPTION
        - None считается как NO_INTERRUPTION
        
        Args:
            other: Запрошенный тип прерывания для проверки
            
        Returns:
            True, если текущий тип покрывает запрошенный
        """
        if other is None:
            other = InterruptionType.NO_INTERRUPTION
        
        # ANY покрывает всё
        if self == InterruptionType.ANY:
            return True
        
        # Точное совпадение
        if self == other:
            return True
        
        # NO_INTERRUPTION покрывает только NO_INTERRUPTION
        if self == InterruptionType.NO_INTERRUPTION:
            return other == InterruptionType.NO_INTERRUPTION
        
        # GENERIC_INTERRUPTION покрывает все конкретные типы
        if self == InterruptionType.GENERIC_INTERRUPTION:
            specific_types = self._get_specific_types()
            return other in specific_types
        
        # Конкретный тип покрывает только себя (уже проверено выше)
        return False

    def intersection(self, other: 'InterruptionType | None') -> 'InterruptionType | None':
        """Вычисляет пересечение двух типов прерываний.
        
        Возвращает более конкретное значение, если типы пересекаются (совместимы),
        или None, если типы не пересекаются.
        
        Логика:
        - Если типы совместимы (оба покрывают общее значение), возвращается более конкретное
        - Порядок конкретности: конкретные типы > GENERIC_INTERRUPTION > NO_INTERRUPTION > ANY
        - Если типы не пересекаются, возвращается None
        
        Args:
            other: Другой тип прерывания для вычисления пересечения
            
        Returns:
            Более конкретное значение из пересечения, или None, если типы не пересекаются
        """
        if other is None:
            other = InterruptionType.NO_INTERRUPTION
        
        # Если типы одинаковые, возвращаем их
        if self == other:
            return self
        
        # Проверяем, пересекаются ли типы...
        # Типы пересекаются, если один покрывает другой (или оба покрывают общее значение)
        self_fits_other = self.fits(other)
        other_fits_self = other.fits(self)
        
        # Если типы не пересекаются (ни один не покрывает другой и они не одинаковые)
        if not self_fits_other and not other_fits_self:
            return None
        
        # Определяем более конкретное значение
        # Порядок конкретности: конкретные типы > GENERIC_INTERRUPTION > NO_INTERRUPTION > ANY
        specific_types = self._get_specific_types()
        
        # Если один из типов - конкретный, он более конкретный
        if self in specific_types:
            if other in specific_types:
                # Оба конкретные, но неодинаковые (одинаковость уже проверена выше)
                return None
            # self конкретный, other - нет, значит self более конкретный
            return self
        if other in specific_types:
            # other конкретный, self - нет, значит other более конкретный
            return other
        
        # Если один из типов - GENERIC_INTERRUPTION
        if self == InterruptionType.GENERIC_INTERRUPTION:
            if other == InterruptionType.ANY:
                return self  # GENERIC_INTERRUPTION более конкретный, чем ANY
            # other должен быть NO_INTERRUPTION, но они не пересекаются
            return None
        if other == InterruptionType.GENERIC_INTERRUPTION:
            if self == InterruptionType.ANY:
                return other  # GENERIC_INTERRUPTION более конкретный, чем ANY
            # self должен быть NO_INTERRUPTION, но они не пересекаются
            return None
        
        # Если один из типов - NO_INTERRUPTION
        if self == InterruptionType.NO_INTERRUPTION:
            if other == InterruptionType.ANY:
                return self  # NO_INTERRUPTION более конкретный, чем ANY
            # other должен быть GENERIC_INTERRUPTION, но они не пересекаются
            assert other == InterruptionType.NO_INTERRUPTION, other
            return None
        if other == InterruptionType.NO_INTERRUPTION:
            if self == InterruptionType.ANY:
                return other  # NO_INTERRUPTION более конкретный, чем ANY
            # self должен быть GENERIC_INTERRUPTION, но они не пересекаются
            assert self == InterruptionType.NO_INTERRUPTION, other
            return None
        
        # Если оба - ANY, возвращаем ANY
        # (равенство проверено выше)
        # if self == InterruptionType.ANY and other == InterruptionType.ANY:
        #     return self
        
        # Fallback (не должно произойти)
        return None

    @classmethod
    def merge(cls, this: Optional['InterruptionType'], other: Optional['InterruptionType']) -> Optional['InterruptionType']:
        """Объединить два типа прерывания согласно правилам:
        - Одинаковые значения → возвращается оно же
        - GENERIC_INTERRUPTION + конкретное → GENERIC_INTERRUPTION
        - NO_INTERRUPTION + GENERIC_INTERRUPTION → ANY
        - Два разных конкретных типа → GENERIC_INTERRUPTION
        - ANY + любое → ANY
        - None подразумевает NO_INTERRUPTION
        """
        # Если оба None
        if this is None and other is None:
            return None
        
        # Если None, то подменяем явным типом
        if this is None:
            this = cls.NO_INTERRUPTION
        if other is None:
            other = cls.NO_INTERRUPTION
        
        # Если одинаковые - возвращаем само значение
        if this == other:
            return this
        
        # ANY + любое = ANY
        if this == cls.ANY or other == cls.ANY:
            return cls.ANY
        
        specific_types = cls._get_specific_types()
        
        # NO_INTERRUPTION + GENERIC_INTERRUPTION = ANY (в любом порядке)
        if (this == cls.NO_INTERRUPTION and other == cls.GENERIC_INTERRUPTION) or \
           (this == cls.GENERIC_INTERRUPTION and other == cls.NO_INTERRUPTION):
            return cls.ANY
        
        # GENERIC_INTERRUPTION + конкретное = GENERIC_INTERRUPTION (в любом порядке)
        if this == cls.GENERIC_INTERRUPTION and other in specific_types:
            return cls.GENERIC_INTERRUPTION
        if other == cls.GENERIC_INTERRUPTION and this in specific_types:
            return cls.GENERIC_INTERRUPTION
        
        # Два разных конкретных типа → GENERIC_INTERRUPTION
        if this in specific_types and other in specific_types:
            return cls.GENERIC_INTERRUPTION
        
        # NO_INTERRUPTION + конкретное → возвращаем ANY
        # По логике: если есть NO_INTERRUPTION и конкретное, то это означает,
        # что прерывание может быть (конкретное) или не быть (NO_INTERRUPTION) = ANY
        if (this == cls.NO_INTERRUPTION and other in specific_types) or \
           (other == cls.NO_INTERRUPTION and this in specific_types):
            return cls.ANY
        
        # Если не подошло ни одно правило, возвращаем более общее значение
        # (приоритет: ANY > GENERIC_INTERRUPTION > конкретные > NO_INTERRUPTION)
        if this == cls.GENERIC_INTERRUPTION:
            return this
        if other == cls.GENERIC_INTERRUPTION:
            return other
        if this in specific_types:
            return this
        if other in specific_types:
            return other
        
        return this  # fallback


class CallStackAction(SelfValidatedEnum):
    """Call stack actions for effects"""
    NONE = "none"
    ADD_FRAME = "add_frame"
    DROP_FRAME = "drop_frame"
    DEFAULT = NONE  # alias


class OptionalBoolValue(SelfValidatedEnum):
    """Condition values for constraints"""
    # true = True
    # false = False
    true = 'true'
    false = 'false'
    NO_VALUE = 'no_value'  # (нет самого условия).
    ANY = 'any'  # при наличии, отсутствии или любом значении.
    DEFAULT = NO_VALUE  # alias

    @classmethod
    def lookup(cls, value, raise_on_error: bool = True):
        """Lookup enum value, converting bool to string if needed."""
        # Преобразуем bool значения в строки для совместимости с YAML
        if isinstance(value, bool):
            value = 'true' if value is True else 'false'
        return super().lookup(value, raise_on_error)


class ActionKind(SelfValidatedEnum):
    """Single values associated with kind of ActionSpec """
    # common useful:
    CONDITION = "condition"  # управляющее условие, в зависимости от значения которого дальнейшее выполнение программы может развиваться по-разному.
    BLOCK = "block"  # блок кода (обособленная последовательность statement'ов).
    # constructs known so far:
    SEQUENCE = "sequence"  # линейная последовательность statement'ов: как block, или глобальный код.
    ALTERNATIVE = "alternative"  # развилка `if...` в любых формах.
    LOOP = "loop"  # общий kind для всех видов циклов
    NOOP = "noop"  # пустое действие: не выполняется в трассе (например, статические определения функций не являются выполняемыми statement'ами в компилируемых ЯП).
    CALL = "call"  # вызов функции.
    TRY = "try"  # try-catch и вариации.
    # basic types
    COMPOUND = "compound"  # нечто составное: блок или алгоритмическая структура.
    INLINE = "inline"  # однострочное действие: простой statement или condition; становится `atom` в CFG, если не содержит вызовов функций.
    # other
    ANY = "any"  # for usage as constraint.
    AUTO = "auto"  # "see underlying Construct instead": в контексте роли действия в структуре не всегда понятен его kind, в этом случае задаётся auto, что означает: надо посмотреть на kind алгоритмической структуры самого действия.


class KindChain:
    """Dot-chained names each of which can be queried separately"""
    chain: list[str]

    def __init__(self, chain: str | list[str] | Self = '', sep='.'):
        if isinstance(chain, str):
            self.chain = chain.split(sep) if chain else []
        elif isinstance(chain, list):
            self.chain = chain
        elif isinstance(chain, type(self)):
            self.chain = chain.chain
        else:
            raise TypeError(f'KindChain\'s "chain" must be str or list, not {type(chain).__name__}')

    def __contains__(self, item):
        return item in self.chain
    has = __contains__

    def is_subset_of(self, other: Self | list[Self]) -> bool:
        return all((item in other) for item in self.chain)

    def to_enums(self) -> list[ActionKind]:
        """ to list of ActionKind instances, filtered & ordered by the enum. """
        known_kinds = []
        # перебор в порядке определения членов ActionKind
        for kind in ActionKind.__members__.values():
            if kind.value in self:
                known_kinds.append(ActionKind.lookup(kind.value))
                # known_kinds.append(ActionKind.__members__[kind])
        return known_kinds

    def __hash__(self):
        return hash(tuple(self.chain))

    def __iter__(self):
        return iter(self.chain)

    def __len__(self):
        return len(self.chain)

    def __str__(self):
        return '.'.join(self.chain)
    __repr__ = __str__


@dataclass
class Effects(DictLikeDataclass):
    """Effects that can be applied to actions or transitions"""
    interruption_stop: Optional[InterruptionType] = InterruptionType.NO_INTERRUPTION
    interruption_start: Optional[InterruptionType] = InterruptionType.NO_INTERRUPTION
    call_stack: Optional[CallStackAction] = CallStackAction.NONE

    @classmethod
    def merge(cls, this: Self, other: Self) -> Self | None:
        """ Объединить эффекты из последовательных узлов/рёбер, заполняя незаполненное, если указано.
         В случае "конфликта" -- в обоих заполнено -- нельзя объединить -- возвращается False.
         """
        if this is not None and not isinstance(this, cls):
            raise TypeError(f"Expected {cls.__name__} instance for 'this', got {type(this)!r}")
        if other is not None and not isinstance(other, cls):
            raise TypeError(f"Expected {cls.__name__} instance for 'other', got {type(other)!r}")

        if this is None:
            return other if other is not None else cls()
        if other is None:
            return this

        result = cls()
        for name in this.keys():
            existing_value = this[name] if other is not None else None
            if existing_value is not None:  ###  and existing_value != 'any':
                result[name] = existing_value
                continue

            new_value = other[name] if this is not None else None
            if new_value is not None and new_value != 'any':
                if result[name] == 'any':
                    result[name] = new_value
                else:
                    # No merging allowed: cannot overwrite meaningful values.
                    return None
        return result

    def changes_interruption_mode(self):
        # Any of interruption_start or interruption_stop is not empty.
        # Note: interruption_stop may be set but not affect actual interruption-state if no interruption has been triggered before during a real program run.
        return (self.interruption_stop is not None or
                self.interruption_start is not None or
                self.interruption_stop != InterruptionType.NO_INTERRUPTION or
                self.interruption_start != InterruptionType.NO_INTERRUPTION)

class WithEffectsMixin:
    def changes_interruption_mode(self):
        """ Retrieves self.effects and checks them for Effects.changes_interruption_mode(). """
        if hasattr(self, 'effects'):
            if isinstance(self.effects, list):
                return any((isinstance(effect, Effects) and effect.changes_interruption_mode())
                           for effect in self.effects)
            if isinstance(self.effects, Effects):
                return self.effects.changes_interruption_mode()
        return False

@dataclass
class Identification(DictLikeDataclass):
    """Identification specification for finding nodes in AST. Internal usage only. """
    origin: Optional[OriginType] = None
    property: Optional[str] = None
    property_path: Optional[str] = None
    role_in_list: Optional[RoleInListType] = None


@dataclass
class Behaviour(DictLikeDataclass):
    """Behaviour for actions"""
    assumed_value: Optional[OptionalBoolValue] = OptionalBoolValue.NO_VALUE  # Подразумеваемое значение условия, когда по контексту оно есть, но может быть опущено. Это значение говорит, как интерпретировать условие, когда условие опушено в коде, т.е. в AST пусто (нет узла).

    # # Additional fields can be added as needed
    # custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class Constraints(DictLikeDataclass):
    """Constraints for transitions"""
    condition_value: Optional[OptionalBoolValue] = OptionalBoolValue.DEFAULT
    interruption_mode: Optional[InterruptionType] = InterruptionType.DEFAULT
    # # Additional constraints can be added as needed
    # custom: dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash((self.condition_value, self.interruption_mode))

    @classmethod
    def merge(cls, this: Self, other: Self) -> Self:
        """ Объединить ограничения из последовательных узлов/рёбер, заполняя незаполненное, если указано.
         В случае "конфликта" -- в обоих заполнено -- используется специальная логика слияния для interruption_mode,
         для остальных полей берётся значение из левого (значение `any` имеет низший приоритет).
         """
        if this is not None and not isinstance(this, cls):
            raise TypeError(f"Expected {cls.__name__} instance for 'this', got {type(this)!r}")
        if other is not None and not isinstance(other, cls):
            raise TypeError(f"Expected {cls.__name__} instance for 'other', got {type(other)!r}")

        # Конвертируем пустоту в осмысленное значение по умолчанию
        if this is None:
            this = cls()
        if other is None:
            other = cls()

        result = cls()
        for name in this.keys():
            existing_value = this[name]
            new_value = other[name]
            
            # Специальная логика для interruption_mode
            if name == 'interruption_mode':
                merged_interruption = InterruptionType.merge(existing_value, new_value)
                result[name] = merged_interruption
                continue
            
            # Для остальных полей - стандартная логика
            if existing_value is not None:  ###  and existing_value != 'any':
                result[name] = existing_value
                continue

            if new_value is not None and result[name] == 'any':
                # rewriting weak `any` value with any  value `new_value` is.
                result[name] = new_value

        return result

    @classmethod
    def chain_merge(cls, this: Self, other: Self) -> Self:
        """Объединить ограничения из последовательных узлов/рёбер в цепочку.
        
        Для interruption_mode выбирает более узкое (конкретное) значение через intersection.
        Для остальных полей использует ту же логику, что и merge (берётся значение из левого,
        значение `any` имеет низший приоритет).
        
        Args:
            this: Первое ограничение
            other: Второе ограничение
            
        Returns:
            Объединённое ограничение с более узким значением для interruption_mode
        """
        if this is not None and not isinstance(this, cls):
            raise TypeError(f"Expected {cls.__name__} instance for 'this', got {type(this)!r}")
        if other is not None and not isinstance(other, cls):
            raise TypeError(f"Expected {cls.__name__} instance for 'other', got {type(other)!r}")

        # Конвертируем пустоту в осмысленное значение по умолчанию
        if this is None:
            this = cls()
        if other is None:
            other = cls()

        result = cls()
        for name in this.keys():
            existing_value = this[name]
            new_value = other[name]
            
            # Специальная логика для interruption_mode: выбираем более узкое значение
            if name == 'interruption_mode':
                # Если оба значения заданы, используем intersection для выбора более узкого
                intersection = (existing_value or InterruptionType.DEFAULT).intersection(new_value or InterruptionType.DEFAULT)
                if intersection is not None:
                    result[name] = intersection
                else:
                    # Если не пересекаются, используем значение из левого (this)
                    result[name] = existing_value
                continue
            
            # Для остальных полей - стандартная логика (как в merge)
            if existing_value is not None:
                result[name] = existing_value
                continue

            if new_value is not None and result[name] == 'any':
                # rewriting weak `any` value with any value `new_value` is.
                result[name] = new_value

        return result



@dataclass
class ActionSpec(DictLikeDataclass):
    role: str
    name: str | None = None
    kind: KindChain = KindChain()
    generalization: str | None = None  # general role
    effects: list[Effects] = field(default_factory=list)
    identification: Identification = field(default_factory=Identification)  # not exported; for CFG construction only.
    behaviour: Behaviour = field(default_factory=Behaviour)
    construct: 'ConstructSpec | None' = None

    def find_node_data(self, wrapped_ast: 'aw.ASTNodeWrapper', previous_action_data: 'aw.ASTNodeWrapper'=None) -> (
            'aw.ASTNodeWrapper | None'):
        """ Extracts data according to requested method of access. """
        if self.role == END:  ### in (BEGIN, END):
            # the construction itself should be returned as data for END
            return wrapped_ast

        return wrapped_ast.get(self.role, self.identification, previous_action_data)


@dataclass
class TransitionSpec(DictLikeDataclass):
    from_: str | None = None
    to: str | None = None
    to_when_absent: list[str] | str | None = None  # A fallback or a chain of fallbacks. (List is first in the Union as more specific for automatic creation/conversion.)
    constraints: Constraints | None = None
    effects: list[Effects] = field(default_factory=list)
    # metadata: Metadata = field(default_factory=Metadata)
    construct: 'ConstructSpec | None' = None

    def to_when_absent_as_list(self) -> list[str]:
        if isinstance(self.to_when_absent, list):
            return self.to_when_absent
        if self.to_when_absent:
            return [self.to_when_absent]
        return []


@dataclass
class ConstructSpec(DictLikeDataclass):
    name: str
    kind: KindChain = field(default_factory=KindChain)
    ast_node: list[str] | str | None = None  # "type" узла в AST по стандарту MeaningTree.
    actions: list[ActionSpec] = field(default_factory=list)
    transitions: list[TransitionSpec] = field(default_factory=list)
    effects: list[Effects] = field(default_factory=list)
    # metadata: Metadata = field(default_factory=Metadata)
    role2action: dict[str, ActionSpec] | None = None  # Заполняется автоматически после создания объекта.

    def __post_init__(self):
        # Add BEGIN and END actions if not present
        for b in (BEGIN, END):
            # add bounds if not defined explicitly.
            if not any(action.role == b for action in self.actions):
                self.actions.append(ActionSpec(role=b, kind=self.kind))

        # re-index actions by role,
        # & set full name based on construct name
        self.role2action = {}
        for action in self.actions:
            self.role2action[action.role] = action
            action.name = self.name + "_" + action.role
            action.construct = self

        # Add construct's Effects to END node
        self.role2action[END].effects += self.effects

        # Bind transitions to self
        for transition in self.transitions:
            transition.construct = self

    def supported_ast_nodes(self) -> list[str]:
        if isinstance(self.ast_node, list):
            return self.ast_node
        if self.ast_node:
            return [self.ast_node]
        return []

    def find_action_by_role(self, role: str) -> Optional[ActionSpec]:
        """ Only one action is mapped to a role.
        But note that several actions can have the same generalization (in this case, any is returned). """
        if role in self.role2action:
            return self.role2action[role]
        # actions = []
        for action in self.actions:
            if action.role == role or action.generalization == role:
                return action
                # actions.append(action)
        return None

    def find_transitions_from_action(self, action: ActionSpec) -> list[TransitionSpec]:
        roles = (action.role, action.generalization)
        return [tr
                for tr in self.transitions
                if tr.from_ in roles]

    def fill_interruption_edges(self):
        """Добавляет переходы по прерываниям из всех действий в конец конструкта (END).
        
        Для каждого действия (кроме BEGIN и END):
        - Если нет переходов с прерываниями, добавляет переход на END с GENERIC_INTERRUPTION
        - Если есть частичное покрытие прерываний, выдает предупреждение в stderr
        
        Полное покрытие считается, если есть:
        - GENERIC_INTERRUPTION (логически включает все виды прерываний), или
        - Все 4 конкретных типа: BREAK, CONTINUE, RETURN, EXCEPTION
        """
        # Конкретные виды прерываний (без GENERIC_INTERRUPTION)
        specific_interruption_types = {
            InterruptionType.BREAK,
            InterruptionType.CONTINUE,
            InterruptionType.RETURN,
            InterruptionType.EXCEPTION,
        }
        
        for action in self.actions:
            # Пропускаем BEGIN и END
            if action.role in (BEGIN, END):
                continue
            
            # Находим все переходы из этого действия
            transitions = self.find_transitions_from_action(action)
            
            # Собираем виды прерываний, которые уже покрыты переходами
            covered_interruptions = set()
            has_any_interruption = False
            has_generic_interruption = False
            
            for tr in transitions:
                if tr.constraints and tr.constraints.interruption_mode:
                    interruption_mode = tr.constraints.interruption_mode
                    # Игнорируем NO_INTERRUPTION, None, ANY
                    if interruption_mode not in (
                        InterruptionType.NO_INTERRUPTION,
                        InterruptionType.ANY,
                        None
                    ):
                        covered_interruptions.add(interruption_mode)
                        has_any_interruption = True
                        if interruption_mode == InterruptionType.GENERIC_INTERRUPTION:
                            has_generic_interruption = True
            
            # Если нет переходов с прерываниями - добавляем GENERIC_INTERRUPTION на END
            if not has_any_interruption:
                # Проверяем, что такого перехода еще нет
                existing_interruption_transition = any(
                    tr.from_ == action.role and
                    tr.to == END and
                    tr.constraints and
                    tr.constraints.interruption_mode == InterruptionType.GENERIC_INTERRUPTION
                    for tr in self.transitions
                )
                
                if not existing_interruption_transition:
                    new_transition = TransitionSpec(
                        from_=action.role,
                        to=END,
                        constraints=Constraints(interruption_mode=InterruptionType.GENERIC_INTERRUPTION),
                        construct=self
                    )
                    self.transitions.append(new_transition)
            
            # Проверяем полноту покрытия
            elif has_any_interruption:
                # Полное покрытие: есть GENERIC_INTERRUPTION или все 4 конкретных типа
                is_full_coverage = (
                    has_generic_interruption or
                    specific_interruption_types.issubset(covered_interruptions)
                )
                
                # Если покрытие неполное - выдаем предупреждение
                if not is_full_coverage:
                    covered_specific = covered_interruptions & specific_interruption_types
                    missing_specific = specific_interruption_types - covered_interruptions
                    print(
                        f"Warning: Incomplete interruption specification for action '{action.role}' "
                        f"in construct '{self.name}'. "
                        f"Covered: {[i.value for i in covered_interruptions]}, "
                        f"Missing specific types: {[i.value for i in missing_specific]}. "
                        f"Consider adding GENERIC_INTERRUPTION or all specific types.",
                        file=sys.stderr
                    )

    def find_target_action_for_transition(
            self,
            tr: TransitionSpec,
            wrapped_ast: 'aw.ASTNodeWrapper',
            previous_wrapped_ast: 'aw.ASTNodeWrapper' = None,
    ) -> tuple[ActionSpec, 'aw.ASTNodeWrapper', bool, list['TransitionSpec']] | None:
        """  Returns related action, node data for it, a flag, and the transition chain:
            flag: True: main output used, False: `to_when_absent` output used.
            transition_chain: list of transitions that led to the target action.
        """
        current_chain = [tr]

        while True:
            for target_role in (tr.to, *tr.to_when_absent_as_list()):
                if target_role:
                    action = self.role2action.get(target_role)
                    if action:
                        target_wrapped_ast = action.find_node_data(wrapped_ast, previous_wrapped_ast)
                        if target_wrapped_ast:
                            return action, target_wrapped_ast, (target_role == tr.to), current_chain

            # for cases where target is absent in AST, search further along transition chain
            # TODO: use assumed value of condition & more heuristics.
            primary_out = tr.to
            primary_action = self.role2action.get(primary_out)
            if not primary_action:
                break
            trs = self.find_transitions_from_action(primary_action)
            if not trs:
                break
            tr = trs[0]
            # not really good to just take the first.. TODO
            if tr in current_chain:
                break  # prevent infinite looping
            current_chain.append(tr)

        # nothing found
        raise ValueError([tr.from_, tr.to, tr.to_when_absent, wrapped_ast.ast_node['id'], previous_wrapped_ast.ast_node['id']])
        # return None


@dataclass
class SituationState(DictLikeDataclass):
    interruption_state: InterruptionType


def load_constructs(path="./constructs.yml", debug=False):
    """ Load constructs.yml using DictLikeDataclass """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found. Please upload constructs.yml to /mnt/data.")

    with open(path, "r", encoding="utf-8") as f:
        raw_yaml = f.read()

    constructs_raw = yaml.safe_load(raw_yaml)
    del raw_yaml

    # Parse constructs into dataclasses using DictLikeDataclass
    constructs = {}
    for cname, cbody in constructs_raw.items():
        # Create ConstructSpec using DictLikeDataclass.make
        cs = ConstructSpec.make({"name": cname, **cbody})
        
        # Заполняем переходы по прерываниям после загрузки
        cs.fill_interruption_edges()

        constructs[cname] = cs

    if debug:
        print("Loaded constructs (summary):")
        for k, v in constructs.items():
            print("-", k, ": actions:", ', '.join(a.role for a in v.actions) or 'none')
            print("   \\ transitions:", ', '.join(f'{t.from_} -> {t.to}' for t in v.transitions) or 'none')

    return constructs


class AppearanceType(SelfValidatedEnum):
    """Show action buttons or not."""
    MANDATORY = "mandatory"
    NONE = "none"
    # OPTIONAL = "optional"


@dataclass
class AppearanceProfile(DictLikeDataclass):
    name: str
    checks: dict[KindChain, AppearanceType]

    def __post_init__(self):
        # sort checks by specificity (len of kind chain) DESC
        self.checks = dict(sorted(self.checks.items(), key=lambda kv: len(kv[0]), reverse=True))

    def get_appearance_for_kind_chain(self, chain: KindChain, role: str | None = None, has_function_calls: bool = False):
        # Если есть вызовы функций и указана роль, сначала ищем специфичные записи
        if has_function_calls and role:
            # Попытка 1: Наиболее специфичное - chain + "WITH_CALLS" + role
            extended_chain_list = chain.chain + ["WITH_CALLS", role]
            extended_chain = KindChain(extended_chain_list)
            # Ищем etalon_chain, который является подмножеством extended_chain
            # (то есть все элементы etalon_chain должны быть в extended_chain)
            for etalon_chain, appearance in self.checks.items():
                if etalon_chain.is_subset_of(extended_chain):
                    return appearance
            
        # Попытка 3: Обычный поиск по исходному chain (для обратной совместимости)
        for etalon_chain, appearance in self.checks.items():
            if etalon_chain.is_subset_of(chain):
                return appearance

        # by default, make it mandatory for all unknown nodes
        return AppearanceType.MANDATORY # "show" for all unknown


def load_appearance_profiles(path="./construct_appearance.yml", debug=False) -> list[AppearanceProfile]:
    """ Loads profiles of action-button appearance from file, following config.
    if `profiles_priority` is present in the file, it is used to reorder profiles.
    Otherwise, result list will contain profiles exactly in the order these written under `profiles`.
     """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found.")

    with open(path, "r", encoding="utf-8") as f:
        raw_yaml = f.read()

    profiles_data_raw = yaml.safe_load(raw_yaml)
    del raw_yaml

    # Extract profiles data and priority
    profiles_data = profiles_data_raw.get('profiles', {})
    profiles_priority = profiles_data_raw.get('profiles_priority', [])

    # Create AppearanceProfile objects
    profiles_list = []
    for profile_name, profile_checks in profiles_data.items():
        # Create AppearanceProfile using DictLikeDataclass.make
        profile = AppearanceProfile.make({
            "name": profile_name,
            "checks": profile_checks
        })
        profiles_list.append(profile)

    # Apply priority ordering if specified
    if profiles_priority:
        # Create a mapping of profile names to profiles
        profile_map = {profile.name: profile for profile in profiles_list}

        # Reorder according to priority
        ordered_profiles = []
        for priority_name in profiles_priority:
            if priority_name in profile_map:
                ordered_profiles.append(profile_map[priority_name])
                del profile_map[priority_name]  # Remove to avoid duplicates

        # Add remaining profiles not in priority list
        ordered_profiles.extend(profile_map.values())
        profiles_list = ordered_profiles

    if debug:
        print("Loaded appearance profiles:")
        for profile in profiles_list:
            print(f"- {profile.name}: {len(profile.checks)} checks")

    return profiles_list


DEFAULT_APPEARANCE_PROFILE = load_appearance_profiles()[0]
assert DEFAULT_APPEARANCE_PROFILE is not None
