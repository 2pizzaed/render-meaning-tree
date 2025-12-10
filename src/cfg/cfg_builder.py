import sys
from typing import Optional

from src.cfg.abstractions import (
    ConstructSpec,
    ActionSpec,
    AppearanceType,
    DEFAULT_APPEARANCE_PROFILE, KindChain,
)
from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.cfg import Node, CFG, BEGIN, END, Metadata, NodeKind
from src.cfg.node_kind_rules import NodeConstruction, determine_node_construction
from src.json_search import search_bfs, search_dfs


FUNC_DEF_CONSTRUCT = 'func_def_structure'
FUNC_CALL_CONSTRUCT = 'func_call_structure'

FUNC_DEF_AST_NODE_TYPES = (
    'function_definition',
    'method_definition',
)

# Глобальный set для отслеживания уже выведенных предупреждений о типах узлов без конструктов
_seen_unknown_construct_types: set[str | None] = set()

# ---------- CFGBuilder ----------
class CFGBuilder:
    constructs: dict[str, ConstructSpec]
    func_cfgs: dict[str, CFG]
    collect_global_functions_only: bool = False

    def __init__(self, constructs_map: dict[str, ConstructSpec], collect_global_functions_only: bool = False):
        self.constructs = constructs_map
        self.func_cfgs = {}
        self.collect_global_functions_only = collect_global_functions_only

    def _determine_node_appearance(
        self,
        *,
        construct: ConstructSpec | None = None,
        action: ActionSpec | None = None,
        role: str | None = None,
        has_function_calls: bool = False,
    ) -> AppearanceType:
        # Если есть action, используем его kind (более специфичен, чем construct.kind)
        # Это важно для узлов тела функции в вызовах, где action.kind=compound, а construct.kind=inline.call
        if action and not action.kind.has('auto'):
            return DEFAULT_APPEARANCE_PROFILE.get_appearance_for_kind_chain(
                action.kind, role=role, has_function_calls=has_function_calls
            )

        # у action есть метка auto: проверяем по типу конструкта...

        if construct and construct.kind:
            construct_kind = construct.kind
        else:
            construct_kind = KindChain()  # empty kind for unknown constructs

        return DEFAULT_APPEARANCE_PROFILE.get_appearance_for_kind_chain(
            construct_kind, role=role, has_function_calls=has_function_calls
        )
        # # by default, make it mandatory for all unknown nodes
        # return AppearanceType.MANDATORY

    def _apply_node_appearance(
        self,
        node_or_pair: Node | tuple[Node, Node] | list[Node] | None,
        *,
        construct: ConstructSpec | None = None,
        action: ActionSpec | None = None,
        has_function_calls: bool = False,
    ) -> None:
        if node_or_pair is None:
            return
        if isinstance(node_or_pair, (tuple, list)):
            for node in node_or_pair:
                self._apply_node_appearance(
                    node, construct=construct, action=action, has_function_calls=has_function_calls
                )
            return

        if not node_or_pair.metadata.wrapped_ast:
            # Пустые и промежуточные действия
            appearance = AppearanceType.NONE
        else:
            # Определяем роль узла
            role = None
            if node_or_pair.role_in_construct == BEGIN or node_or_pair.kind == NodeKind.BEGIN:
                role = BEGIN
            elif node_or_pair.role_in_construct == END or node_or_pair.kind == NodeKind.END:
                role = END
            
            appearance = self._determine_node_appearance(
                construct=construct, action=action, role=role, has_function_calls=has_function_calls
            )
        
        node_or_pair.appearance = appearance

    def _create_simple_cfg(self, name: str) -> CFG:
        """Создает простой самосвязанный CFG из одного узла."""
        return CFG.create_empty(name)

    def find_construct_for_astnode(self, ast_node_wrapper: ASTNodeWrapper) -> Optional[ConstructSpec]:
        v = ast_node_wrapper.ast_node
        if isinstance(v, dict):
            node_type = v.get("type")
            for construct in self.constructs.values():
                if node_type in construct.supported_ast_nodes():
                    return construct
            ###
            # Выводим предупреждение только один раз для каждого типа узла
            if node_type not in _seen_unknown_construct_types:
                print(f'Note: no construct found for ast_node {node_type=}, treating as atomic.', file=sys.stderr)
                _seen_unknown_construct_types.add(node_type)
            ###
        return None

    def _extract_function_name(self, wrapped_ast: ASTNodeWrapper, construct: ConstructSpec) -> Optional[str]:
        """Извлекает имя функции из AST узла, используя action с ролью 'name' из конструкта."""
        # Находим action с ролью 'name' в конструкте
        name_action = None
        for action in construct.actions:
            if action.role == 'name':
                name_action = action
                break
        
        if not name_action:
            print(f"Warning: no name action found in construct {construct.name}", file=sys.stderr)
            print(f'Available actions: {[a.role for a in construct.actions]}')
            return None
        
        # Извлекаем данные узла с именем функции
        name_data = name_action.find_node_data(wrapped_ast)
        if not name_data:
            print(f"Warning: could not extract function name from AST", file=sys.stderr)
            return None
        
        # Получаем имя функции из AST узла
        if isinstance(name_data.ast_node, dict):
            func_name = name_data.ast_node.get('name')
        elif isinstance(name_data.ast_node, str):
            func_name = name_data.ast_node
        else:
            print(
                f"Warning: unexpected AST node type for function name: {type(name_data.ast_node)}",
                file=sys.stderr,
            )
            return None
        
        if not func_name:
            print(f"Warning: function name not found in AST node", file=sys.stderr)
            return None
        
        return func_name

    def _collect_function_definitions(self, ast_node: dict) -> None:
        """
        Предварительно собирает все определения функций из AST дерева.
        
        Args:
            ast_node: Корневой узел AST для поиска определений функций
        """
        # Предикат для поиска узлов определений функций
        def is_function_definition(ast_node_):
            return isinstance(ast_node_, dict) and ast_node_.get('type') in FUNC_DEF_AST_NODE_TYPES
        
        if self.collect_global_functions_only:
            # Поиск только на верхнем уровне (в body программы)
            if isinstance(ast_node, dict) and ast_node.get('type') == 'program_entry_point':
                body = ast_node.get('body', [])
                if isinstance(body, list):
                    for item in body:
                        if is_function_definition(item):
                            self._process_function_definition_node(item)
        else:
            # Поиск по всему дереву AST
            function_def_nodes = search_bfs(ast_node, is_function_definition)
            for func_node in function_def_nodes:
                self._process_function_definition_node(func_node)

        if self.func_cfgs:
            print(
                f"INFO: prepared {len(self.func_cfgs)} CFG(s) for func definition(s): {', '.join(self.func_cfgs.keys())}",
                file=sys.stderr,
            )

    def _process_function_definition_node(self, func_node: dict) -> None:
        """
        Обрабатывает узел определения функции и создает для него CFG.
        
        Args:
            func_node: AST узел определения функции
        """
        # Извлекаем имя функции
        func_name = self._extract_function_name_from_node(func_node)
        if not func_name:
            print(
                f"Warning: could not extract function name from function definition node",
                file=sys.stderr,
            )
            return
        
        # Проверяем, не была ли функция уже обработана
        if func_name in self.func_cfgs:
            raise NotImplementedError(f"Multiple definitions of function '{func_name}' encountered in input AST! This is not supported yet, aborting.")

        # Создаем CFG для функции
        wrapped_ast = ASTNodeWrapper(ast_node=func_node)
        construct = self.find_construct_for_astnode(wrapped_ast)
        if construct:
            self._handle_function_definition(construct, wrapped_ast)
        else:
            print(
                f'Warning: no construct found for function definition "{func_name}"',
                file=sys.stderr,
            )

    def _extract_function_name_from_node(self, func_node: dict) -> Optional[str]:
        """
        Извлекает имя функции из AST узла определения функции.
        
        Args:
            func_node: AST узел определения функции
            
        Returns:
            Имя функции или None если не удалось извлечь
        """
        try:
            # Путь к имени функции согласно структуре в constructs.yml
            # property_path: 'declaration / name / name'
            declaration = func_node.get('declaration')
            if not isinstance(declaration, dict):
                return None
            
            name_node = declaration.get('name')
            if not isinstance(name_node, dict):
                return None
            
            func_name = name_node.get('name')
            if not func_name:
                return None
            
            return func_name
        except (AttributeError, KeyError, TypeError):
            return None

    def _find_function_calls_in_ast(self, ast_node: dict, keep_defined_only=True) -> list[dict]:
        """
        Находит все вызовы функций в AST узле.
        
        Использует поиск в глубину для получения результатов в порядке вычисления
        (сначала самые глубокие, слева направо).
        
        Args:
            ast_node: AST узел для поиска вызовов функций
            
        Returns:
            Список найденных узлов вызовов функций в порядке вычисления
        """
        # Предикат для поиска узлов вызовов функций
        def is_function_call(node):
            return isinstance(node, dict) and node.get('type') == 'function_call'

        found_ast_nodes = search_dfs(ast_node, is_function_call)
        if keep_defined_only:
            found_ast_nodes = [
                ast_node
                for ast_node in found_ast_nodes
                if self._extract_function_name_from_call_node(ast_node) in self.func_cfgs
            ]
        return found_ast_nodes

    def _extract_function_name_from_call_node(self, call_node: dict) -> Optional[str]:
        """
        Извлекает имя функции из AST узла вызова функции.
        
        Args:
            call_node: AST узел вызова функции
            
        Returns:
            Имя функции или None если не удалось извлечь
        """
        try:
            # Путь к имени функции согласно структуре в constructs.yml
            # property_path: 'function / name'
            function_node = call_node.get('function')
            if not isinstance(function_node, dict):
                return None
            
            func_name = function_node.get('name')
            if not func_name:
                return None
            
            return func_name
        except (AttributeError, KeyError, TypeError):
            return None

    def _inject_function_calls_in_cfg(self, base_cfg: CFG, function_calls: list[dict], parent_action: ActionSpec | None = None, wrapped_ast: ASTNodeWrapper | None = None, construct: ConstructSpec | None = None) -> CFG:
        """
        Обрабатывает найденные вызовы функций и встраивает их в CFG.
        
        Args:
            base_cfg: Базовый (пустой) CFG для встраивания вызовов
            function_calls: Список найденных узлов AST с вызовами функций в порядке вычисления
            parent_action: ActionSpec для родительского действия, содержащего вызовы функций
            wrapped_ast: Обёртка AST узла действия
            construct: ConstructSpec для действия

        Returns:
            CFG с встроенными вызовами функций
        """
        if not function_calls:
            return base_cfg
        
        # Если parent_action не None, устанавливаем метаданные для BEGIN/END узлов
        if parent_action is not None:
            base_cfg.begin_node.role_in_construct = parent_action.role
            base_cfg.end_node.role_in_construct = parent_action.role
            base_cfg.begin_node.metadata.abstract_action = parent_action
            base_cfg.end_node.metadata.abstract_action = parent_action
            if wrapped_ast is not None:
                base_cfg.begin_node.metadata.wrapped_ast = wrapped_ast
                base_cfg.end_node.metadata.wrapped_ast = wrapped_ast
        
        # Создаем цепочку вызовов функций
        current_node = base_cfg.begin_node
        
        for call_node in function_calls:
            func_name = self._extract_function_name_from_call_node(call_node)
            if not func_name:
                continue
            
            # Проверяем наличие определения функции
            func_cfg = self.func_cfgs.get(func_name)
            if not func_cfg:
                print(
                    f'Warning: function "{func_name}" not found in func_cfgs, skipping call',
                    file=sys.stderr,
                )
                continue
            
            # Создаем CFG для вызова функции
            call_wrapped_ast = ASTNodeWrapper(ast_node=call_node)
            call_construct = self.find_construct_for_astnode(call_wrapped_ast)
            
            if call_construct and call_construct.name == FUNC_CALL_CONSTRUCT:
                # Используем существующий механизм обработки вызовов
                call_cfg = self._make_cfg_for_function_call(call_construct, call_wrapped_ast)
            else:
                raise ValueError(call_node)
            
            if call_cfg:
                # Добавляем содержимое CFG вызова функции в основной CFG.
                base_cfg.merge(call_cfg)
                # Встраиваем CFG вызова в цепочку
                base_cfg.connect(current_node, call_cfg.begin_node)
                current_node = call_cfg.end_node
        
        # Соединяем последний вызов с концом базового CFG
        base_cfg.connect(current_node, base_cfg.end_node)
        
        # Применяем appearance для BEGIN/END узлов с учетом вызовов функций
        if parent_action is not None:
            self._apply_node_appearance(
                base_cfg.begin_node, 
                construct=construct, 
                action=parent_action, 
                has_function_calls=True
            )
            self._apply_node_appearance(
                base_cfg.end_node, 
                construct=construct, 
                action=parent_action, 
                has_function_calls=True
            )
        
        return base_cfg

    def _create_simple_function_call_cfg(self, func_name: str, wrapped_ast: ASTNodeWrapper) -> CFG:
        """
        Создает простой CFG для вызова функции без использования конструкта.
        
        Args:
            func_name: Имя вызываемой функции
            wrapped_ast: Обёртка AST узла вызова
            
        Returns:
            CFG для вызова функции
        """
        raise DeprecationWarning()
        func_cfg = self.func_cfgs.get(func_name)
        if not func_cfg:
            return None
        
        call_cfg = CFG("simple_function_call")
        
        # Встраиваем CFG функции как subgraph
        func_node_pair = call_cfg.add_node(
            kind=NodeKind.BEGIN,
            role='func',
            metadata=Metadata(
                wrapped_ast=wrapped_ast,
                primary=True,
            ),
            subgraph=func_cfg
        )
        
        # Создаем рёбра BEGIN -> func -> END
        call_cfg.connect(call_cfg.begin_node, func_node_pair[0])
        call_cfg.connect(func_node_pair[1], call_cfg.end_node)
        
        return call_cfg

    def _handle_function_definition(self, construct: ConstructSpec, wrapped_ast: ASTNodeWrapper) -> CFG:
        """Обрабатывает определение функции: создает CFG для тела функции и сохраняет в func_cfgs."""
        # Извлекаем имя функции
        func_name = self._extract_function_name(wrapped_ast, construct)
        if not func_name:
            print(
                f"Warning: could not extract function name, skipping function definition",
                file=sys.stderr,
            )
            # Возвращаем пустой CFG
            return self._create_simple_cfg("empty_function_def")
        
        # Проверка на дублирование определений ф-ии в коде.
        if func_name in self.func_cfgs:
            raise NotImplementedError(f"Multiple definitions of function '{func_name}' encountered in input AST! This is not supported yet, aborting.")

        # Создаем пустой CFG для функции и сохраняем его в словаре.
        # Это нужно, чтобы рекурсивное обращение видело обёртку CFG и могло использовать границы для добавления рёбер ещё до полного определения.
        self.func_cfgs[func_name] = func_cfg = CFG("func_" + func_name)

        # Наполняем CFG для тела функции
        body_wast = wrapped_ast.get('body')
        body_construct = self.find_construct_for_astnode(body_wast)
        self.make_cfg_for_construct(body_construct, body_wast, cfg=func_cfg)

        if 0:
            # not used so far.
            # Возвращаем пустой CFG (чтобы определение не попало в основной поток)
            cfg = self._create_simple_cfg(f"function_{func_name}_definition_registered")

            print(f'INFO: made CFG for **DEF** of func `{func_name}`', 'id: ', wrapped_ast.ast_node.get('id'),
                  file=sys.stderr)

            return cfg

    def _make_cfg_for_function_call(self, construct: ConstructSpec, wrapped_ast: ASTNodeWrapper) -> CFG:
        """Обрабатывает вызов функции: связывает с CFG функции из func_cfgs."""
        # Извлекаем имя функции
        func_name = self._extract_function_name(wrapped_ast, construct)
        if not func_name:
            print(
                f"Warning: could not extract function name, treating as regular compound",
                file=sys.stderr,
            )
            # Обрабатываем как обычный compound без call stack эффектов
            return self.make_cfg_for_construct(construct, wrapped_ast)
        
        # Ищем CFG функции в func_cfgs
        func_cfg = self.func_cfgs.get(func_name)
        if not func_cfg:
            print(
                f'Warning: function "{func_name}" not found in func_cfgs, treating as regular compound',
                file=sys.stderr,
            )
            # Обрабатываем как обычный compound, без эффектов call_stack
            return self.make_cfg_for_construct(construct, wrapped_ast)
        
        # Создаем CFG вызова, встраивая CFG функции
        # Создаем CFG через конструкт, но заменяем тело функции на сохраненный CFG
        call_cfg = CFG("function_call", construct=construct)
        
        # Добавляем метаданные: узел AST (abstract_action уже установлен через construct)
        # Важно: устанавливаем wrapped_ast ДО вызова _apply_node_appearance,
        # чтобы узлы вызова получили правильный appearance
        call_cfg.begin_node.metadata.wrapped_ast = wrapped_ast
        call_cfg.end_node.metadata.wrapped_ast = wrapped_ast
        
        self._apply_node_appearance(
            call_cfg.begin_node,
            construct=construct,
            action=construct.role2action.get(BEGIN),
        )
        self._apply_node_appearance(
            call_cfg.end_node,
            construct=construct,
            action=construct.role2action.get(END),
        )
        
        # Встраиваем CFG функции как subgraph
        func_node_pair = call_cfg.add_node(
            kind=NodeKind.BEGIN,
            role='func',
            # metadata=Metadata(
            #     abstract_action=construct.role2action['func'],
            #     wrapped_ast=wrapped_ast,
            #     primary=True,
            # ),
            subgraph=func_cfg
        )
        self._apply_node_appearance(
            func_node_pair,
            construct=construct,
            action=construct.role2action.get('func'),
        )
        
        # Создаем рёбра, связывая с абстрактными переходами с эффектами call_stack
        # BEGIN -> func (с эффектом add_frame)
        begin_to_func_transition = construct.find_transitions_from_action(construct.role2action[BEGIN])[0]
        call_cfg.connect(call_cfg.begin_node, func_node_pair[0], metadata=Metadata(
            abstract_transition=begin_to_func_transition,
        ))
        
        # func -> END (с эффектом drop_frame)
        func_to_end_transition = construct.find_transitions_from_action(construct.role2action['func'])[0]
        call_cfg.connect(func_node_pair[1], call_cfg.end_node, metadata=Metadata(
            abstract_transition=func_to_end_transition,
        ))
        
        # Увеличиваем счётчик вызовов
        func_cfg.begin_node.metadata.call_count += 1

        print(
            f"INFO: made CFG for call of func `{func_name}`",
            "id: ",
            wrapped_ast.ast_node.get("id"),
            file=sys.stderr,
        )

        return call_cfg

    def make_cfg_for_ast(self, wrapped_ast: ASTNodeWrapper, parent_action: ActionSpec | None = None) -> CFG | None:
        """
        Make CFG for AST node.
        Алгоритм:
        * определить конструкт
        * для составных конструктов выполнить обычное построение.
        * для атомарных однострочных структур (а также неопределённых структур, которые должны быть однострочными действиями):
            выполнить поиск вложенных вызовов функций, создать для них обёртку в случае наличие вызовов, и простой тривиальный cfg в случае отсутствия вызовов.

        Параллельно с созданием узлов CFG к ним необходимо прицеплять (копировать) эффекты и ограничения из абстракций.


        Args:
            wrapped_ast:

        Returns:
            CFG for a compound node or None for an atom.
        """
        is_program_root = isinstance(wrapped_ast.ast_node, dict) and wrapped_ast.ast_node.get('type') == 'program_entry_point'
        # Предварительный сбор определений функций, если это корневой узел программы
        if is_program_root:
            self._collect_function_definitions(wrapped_ast.ast_node)


        construct = self.find_construct_for_astnode(wrapped_ast)
        if construct:
            # Проверяем специальные случаи для функций
            if construct.name == FUNC_DEF_CONSTRUCT:
                # Извлекаем имя функции
                func_name = self._extract_function_name(wrapped_ast, construct)
                if func_name == 'main' and self.func_cfgs and 'main' in self.func_cfgs.keys():
                    # get already prepared CFG for func def
                    return self.func_cfgs['main']
                else:
                    # no-op
                    return None
            elif construct.name == FUNC_CALL_CONSTRUCT:
                return self._make_cfg_for_function_call(construct, wrapped_ast)

        # Обычные узлы
        cfg = self.make_cfg_for_construct(construct, wrapped_ast, parent_action=parent_action)

        # if is_program_root:
        #     # добавить все определения функций
        #     for func_cfg in self.func_cfgs.values():
        #         cfg.merge(func_cfg)
                
        return cfg


    def make_cfg_for_construct(self, construct: ConstructSpec | None, wrapped_ast: ASTNodeWrapper, cfg: CFG = None, parent_action: ActionSpec | None = None) -> CFG | None:
        """
        Make CFG for AST node of known construct, or when no construct exists for this AST node.
        Алгоритм:
        * определить конструкт
        * для составных конструктов выполнить обычное построение.
        * для атомарных однострочных структур (а также неопределённых структур, которые должны быть однострочными действиями):
            выполнить поиск вложенных вызовов функций, создать для них обёртку в случае наличие вызовов, и простой тривиальный cfg в случае отсутствия вызовов.
        """
        construct_kind = construct.kind if construct else None
        construction = determine_node_construction(
            action_kind=construct_kind,  #  Action просто неизвестно, и это не должно повлиять на логику.
            construct_kind=construct_kind,
        )

        if construction is NodeConstruction.NONE:
            return None

        if construction is NodeConstruction.COMPOUND and construct and construct.kind.has('compound'):
            return self.make_cfg_for_compound(construct, wrapped_ast, cfg)

        cfg_name = "atom_" + (construct.name if construct else 'unknown')
        function_calls = ()
        if isinstance(wrapped_ast.ast_node, dict):
            function_calls = self._find_function_calls_in_ast(wrapped_ast.ast_node)

        if function_calls:
            base_cfg = CFG(cfg_name)
            return self._inject_function_calls_in_cfg(base_cfg, function_calls, parent_action=parent_action, wrapped_ast=wrapped_ast, construct=construct)

        metadata = Metadata(wrapped_ast=wrapped_ast)
        atomic_cfg = CFG.create_atomic(cfg_name, metadata=metadata)
        self._apply_node_appearance(atomic_cfg.begin_node, construct=construct)
        return atomic_cfg

    def make_cfg_for_compound(self, construct: ConstructSpec, wrapped_ast: ASTNodeWrapper, cfg: CFG = None) -> CFG:
        """ Предполагается, что CFG для подчинённых узлов будут созданы рекурсивно и встроены в результат.
        Если `cfg` передан, то будет использован для наполнения, иначе создан новый.
        """
        if not cfg:
            # Make fresh CFG.
            ast_node = wrapped_ast.ast_node
            cfg_name = ast_node['type'] if isinstance(ast_node, dict) and 'type' in ast_node else str(ast_node)
            cfg = CFG(cfg_name, construct=construct)

        # Добавить метаданные: узел AST (abstract_action уже установлен через construct)
        cfg.begin_node.metadata.wrapped_ast = wrapped_ast
        cfg.end_node.metadata.wrapped_ast = wrapped_ast
        if construct:
            self._apply_node_appearance(cfg.begin_node, construct=construct, action=construct.role2action.get(BEGIN))
            self._apply_node_appearance(cfg.end_node, construct=construct, action=construct.role2action.get(END))

        # Применить все переходы, попутно создавая узлы,
        # с учётом множественности и повторения ...

        unprocessed_pool = [cfg.begin_node]
        processed_ids = set()

        while unprocessed_pool:
            node = unprocessed_pool.pop(0)
            if node.id in processed_ids:
                continue
            processed_ids.add(node.id)

            role = node.role_in_construct
            # Построить выходящие переходы
            action = construct.role2action.get(role)
            if not action:
                print(
                    f"Error: no action found for role {role} in construct {construct.name}. Trying to continue building CFG...",
                    file=sys.stderr,
                )
                continue
            outgoing_transitions = construct.find_transitions_from_action(action)
            if not outgoing_transitions:
                assert role == END, f'{construct.name=} has no outgoing transitions for {role=}, and this is not END'
            for tr in outgoing_transitions:
                # resolve target action
                try:
                    step_further_tuple = construct.find_target_action_for_transition(
                        tr, wrapped_ast,
                        node.metadata.wrapped_ast)
                except ValueError as e:
                    print(
                        f"Warning: could not resolve transition {tr.from_} -> {tr.to} (or {tr.to_when_absent})",
                        file=sys.stderr,
                    )
                    print(f'  Action: {action.role}, AST: {wrapped_ast.describe()}')
                    print(f'  Error: {e!r}')
                    continue

                target_action, next_wrapped_ast, is_primary, transition_chain = step_further_tuple

                # Check if node for this role already exists
                existing_node = None
                for existing in cfg.nodes.values():
                    if (existing.role_in_construct == target_action.role and
                        existing.metadata.wrapped_ast and
                        existing.metadata.wrapped_ast.ast_node == next_wrapped_ast.ast_node):
                        existing_node = existing
                        break

                if existing_node:
                    # reuse node: usually implies looping.
                    node23 = existing_node
                else:
                    # Make nodes/subgraph for this role...
                    target_construct = self.find_construct_for_astnode(next_wrapped_ast)
                    sub_cfg = self.make_cfg_for_ast(next_wrapped_ast, parent_action=target_action)
                    node_metadata = Metadata(
                        abstract_action=target_action,
                        wrapped_ast=next_wrapped_ast,
                        primary=is_primary,
                    )
                    if sub_cfg:
                        # Implode subCFG & polyfill ends metadata.
                        cfg.merge(sub_cfg)
                        sub_cfg.begin_node.metadata = sub_cfg.end_node.metadata = node_metadata
                        sub_cfg.begin_node.role_in_construct = sub_cfg.end_node.role_in_construct = target_action.role
                        node23 = sub_cfg.begin_node, sub_cfg.end_node
                    else:
                        # No subCFG returned, make trivial transit node.
                        node23 = cfg.add_node(
                            kind=NodeKind.ATOM,  # BEGIN & END will be set automatically, if sub_cfg is non-empty.
                            role=target_action.role,
                            metadata=node_metadata,
                            # subgraph=sub_cfg
                        )
                        self._apply_node_appearance(
                            node23,
                            construct=target_construct,
                            action=target_action,
                        )

                node_pair: tuple[Node, Node] = (node23 if isinstance(node23, tuple) else (node23, node23))

                # connect along the transition found
                cfg.connect(node, node_pair[0], metadata=Metadata(
                    abstract_transition=tr,
                    is_after_last=not is_primary,
                ))

                # последний узел (выходной) добавить в пул необработанных
                next_node = node_pair[1]
                if next_node.id not in processed_ids:
                    unprocessed_pool.append(next_node)

                # начальный узел составного действия будем считать обработанным
                if node_pair[0] is not node_pair[1]:
                    processed_ids.add(node_pair[0].id)
            # end of for.
        return cfg
