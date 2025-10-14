from typing import Optional

from src.cfg.abstractions import ConstructSpec
from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.cfg import Node, CFG, BEGIN, END, Metadata
from src.json_search import search_bfs, search_dfs


FUNC_DEF_CONSTRUCT = 'func_def_structure'
FUNC_CALL_CONSTRUCT = 'func_call_structure'


# ---------- CFGBuilder ----------
class CFGBuilder:
    constructs: dict[str, ConstructSpec]
    func_cfgs: dict[str, CFG]

    def __init__(self, constructs_map: dict[str, ConstructSpec], collect_global_functions_only: bool = False):
        self.constructs = constructs_map
        self.func_cfgs = {}
        self.collect_global_functions_only = collect_global_functions_only

    def _create_simple_cfg(self, name: str) -> CFG:
        """Создает простой самосвязанный CFG из двух узлов (BEGIN и END) и одного ребра."""
        cfg = CFG(name)
        cfg.connect(cfg.begin_node, cfg.end_node)
        return cfg

    def find_construct_for_astnode(self, ast_node_wrapper: ASTNodeWrapper) -> Optional[ConstructSpec]:
        v = ast_node_wrapper.ast_node
        if isinstance(v, dict):
            node_type = v.get("type")
            for construct in self.constructs.values():
                if construct.ast_node == node_type:
                    return construct
            ###
            print(f'Note: no construct found for ast_node {node_type=}')
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
            print(f'Warning: no name action found in construct {construct.name}')
            print(f'Available actions: {[a.role for a in construct.actions]}')
            return None
        
        # Извлекаем данные узла с именем функции
        name_data = name_action.find_node_data(wrapped_ast)
        if not name_data:
            print(f'Warning: could not extract function name from AST')
            return None
        
        # Получаем имя функции из AST узла
        if isinstance(name_data.ast_node, dict):
            func_name = name_data.ast_node.get('name')
        elif isinstance(name_data.ast_node, str):
            func_name = name_data.ast_node
        else:
            print(f'Warning: unexpected AST node type for function name: {type(name_data.ast_node)}')
            return None
        
        if not func_name:
            print(f'Warning: function name not found in AST node')
            return None
        
        return func_name

    def _collect_function_definitions(self, ast_node: dict) -> None:
        """
        Предварительно собирает все определения функций из AST дерева.
        
        Args:
            ast_node: Корневой узел AST для поиска определений функций
        """
        # Предикат для поиска узлов определений функций
        def is_function_definition(node):
            return isinstance(node, dict) and node.get('type') == 'function_definition'
        
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
            print(f'INFO: prepared {len(self.func_cfgs)} CFG(s) for func definition(s): {', '.join(self.func_cfgs.keys())}')

    def _process_function_definition_node(self, func_node: dict) -> None:
        """
        Обрабатывает узел определения функции и создает для него CFG.
        
        Args:
            func_node: AST узел определения функции
        """
        # Извлекаем имя функции
        func_name = self._extract_function_name_from_node(func_node)
        if not func_name:
            print(f'Warning: could not extract function name from function definition node')
            return
        
        # Проверяем, не была ли функция уже обработана
        if func_name in self.func_cfgs:
            raise NotImplementedError(f"Multiple definitions of function '{func_name}' encountered in input AST! This is not supported yet, aborting.")
            return
        
        # Создаем CFG для функции
        wrapped_ast = ASTNodeWrapper(ast_node=func_node)
        construct = self.find_construct_for_astnode(wrapped_ast)
        if construct:
            self._handle_function_definition(construct, wrapped_ast)
        else:
            print(f'Warning: no construct found for function definition "{func_name}"')

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

    def _find_function_calls_in_ast(self, ast_node: dict) -> list[dict]:
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
        
        return search_dfs(ast_node, is_function_call)

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

    def _process_function_calls_in_cfg(self, base_cfg: CFG, function_calls: list[dict]) -> CFG:
        """
        Обрабатывает найденные вызовы функций и встраивает их в CFG.
        
        Args:
            base_cfg: Базовый (пустой) CFG для встраивания вызовов
            function_calls: Список найденных узлов AST с вызовами функций в порядке вычисления

        Returns:
            CFG с встроенными вызовами функций
        """
        if not function_calls:
            return base_cfg
        
        # Создаем цепочку вызовов функций
        current_node = base_cfg.begin_node
        
        for call_node in function_calls:
            func_name = self._extract_function_name_from_call_node(call_node)
            if not func_name:
                continue
            
            # Проверяем наличие определения функции
            func_cfg = self.func_cfgs.get(func_name)
            if not func_cfg:
                print(f'Warning: function "{func_name}" not found in func_cfgs, skipping call')
                continue
            
            # Создаем CFG для вызова функции
            call_wrapped_ast = ASTNodeWrapper(ast_node=call_node)
            construct = self.find_construct_for_astnode(call_wrapped_ast)
            
            if construct and construct.name == FUNC_CALL_CONSTRUCT:
                # Используем существующий механизм обработки вызовов
                call_cfg = self._handle_function_call(construct, call_wrapped_ast)
            else:
                raise ValueError(call_node)
                # Создаем простой CFG для вызова
                call_cfg = self._create_simple_function_call_cfg(func_name, call_wrapped_ast)
            
            if call_cfg:
                # Увеличиваем счётчик вызовов
                func_cfg.begin_node.metadata.call_count += 1
                print(f'CALL++(1) of `{func_name}` =', func_cfg.begin_node.metadata.call_count)

                # Встраиваем CFG вызова в цепочку
                base_cfg.connect(current_node, call_cfg.begin_node)
                current_node = call_cfg.end_node
        
        # Соединяем последний вызов с концом базового CFG
        base_cfg.connect(current_node, base_cfg.end_node)
        
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
            kind='func_body',
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
            print(f'Warning: could not extract function name, skipping function definition')
            # Возвращаем пустой CFG
            return self._create_simple_cfg("empty_function_def")
        
        # Создаем пустой CFG для функции и сохраняем его в словаре.
        # Это нужно, чтобы рекурсивное обращение видело обёртку CFG и могло использовать границы для добавления рёбер ещё до полного определения.
        if func_name in self.func_cfgs:
            raise NotImplementedError(f"Multiple definitions of function '{func_name}' encountered in input AST! This is not supported yet, aborting.")
        self.func_cfgs[func_name] = func_cfg = CFG("func_" + func_name)

        # Наполняем CFG для тела функции
        self.make_cfg_for_construct(construct, wrapped_ast, cfg=func_cfg)

        # Возвращаем пустой CFG (чтобы определение не попало в основной поток)
        cfg = self._create_simple_cfg(f"function_{func_name}_definition_registered")

        print(f'INFO: made CFG for **DEF** of func `{func_name}`', 'id: ', wrapped_ast.ast_node.get('id'))

        return cfg

    def _handle_function_call(self, construct: ConstructSpec, wrapped_ast: ASTNodeWrapper) -> CFG:
        """Обрабатывает вызов функции: связывает с CFG функции из func_cfgs."""
        # Извлекаем имя функции
        func_name = self._extract_function_name(wrapped_ast, construct)
        if not func_name:
            print(f'Warning: could not extract function name, treating as regular compound')
            # Обрабатываем как обычный compound без call stack эффектов
            return self.make_cfg_for_construct(construct, wrapped_ast)
        
        # Ищем CFG функции в func_cfgs
        func_cfg = self.func_cfgs.get(func_name)
        if not func_cfg:
            print(f'Warning: function "{func_name}" not found in func_cfgs, treating as regular compound')
            # Обрабатываем как обычный compound, без эффектов call_stack
            return self.make_cfg_for_construct(construct, wrapped_ast)
        
        # Создаем CFG вызова, встраивая CFG функции
        # Создаем CFG через конструкт, но заменяем тело функции на сохраненный CFG
        call_cfg = CFG("function_call")
        
        # Добавляем метаданные к begin и end узлам
        call_cfg.begin_node.metadata.abstract_action = construct.id2action[BEGIN]
        call_cfg.begin_node.metadata.wrapped_ast = wrapped_ast
        call_cfg.end_node.metadata.abstract_action = construct.id2action[END]
        call_cfg.end_node.metadata.wrapped_ast = wrapped_ast
        
        # Встраиваем CFG функции как subgraph
        func_node_pair = call_cfg.add_node(
            kind='func_body',
            role='func',
            metadata=Metadata(
                abstract_action=construct.id2action['func'],
                wrapped_ast=wrapped_ast,
                primary=True,
            ),
            subgraph=func_cfg
        )
        
        # Создаем рёбра, связывая с абстрактными переходами с эффектами call_stack
        # BEGIN -> func (с эффектом add_frame)
        begin_to_func_transition = construct.find_transitions_from_action(construct.id2action[BEGIN])[0]
        call_cfg.connect(call_cfg.begin_node, func_node_pair[0], metadata=Metadata(
            abstract_transition=begin_to_func_transition,
        ))
        
        # func -> END (с эффектом drop_frame)
        func_to_end_transition = construct.find_transitions_from_action(construct.id2action['func'])[0]
        call_cfg.connect(func_node_pair[1], call_cfg.end_node, metadata=Metadata(
            abstract_transition=func_to_end_transition,
        ))
        
        # Увеличиваем счётчик вызовов
        func_cfg.begin_node.metadata.call_count += 1
        print(f'CALL++(2) of `{func_name}` =', func_cfg.begin_node.metadata.call_count)

        print(f'INFO: made CFG for call of func `{func_name}`', 'id: ', wrapped_ast.ast_node.get('id'))

        return call_cfg

    def make_cfg_for_ast(self, wrapped_ast: ASTNodeWrapper) -> CFG | None:
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
        # Предварительный сбор определений функций, если это корневой узел программы
        if isinstance(wrapped_ast.ast_node, dict) and wrapped_ast.ast_node.get('type') == 'program_entry_point':
            self._collect_function_definitions(wrapped_ast.ast_node)
        
        construct = self.find_construct_for_astnode(wrapped_ast)
        if construct:
            # Проверяем специальные случаи для функций
            if construct.name == FUNC_DEF_CONSTRUCT:
                return self._create_simple_cfg(f"function_def_{construct.name}")
            elif construct.name == FUNC_CALL_CONSTRUCT:
                return self._handle_function_call(construct, wrapped_ast)

        # Обычные узлы
        cfg = self.make_cfg_for_construct(construct, wrapped_ast)
        return cfg


    def make_cfg_for_construct(self, construct: ConstructSpec | None, wrapped_ast: ASTNodeWrapper, cfg: CFG = None) -> CFG:
        """
        Make CFG for AST node of known construct, or when no construct exists for this AST node.
        Алгоритм:
        * определить конструкт
        * для составных конструктов выполнить обычное построение.
        * для атомарных однострочных структур (а также неопределённых структур, которые должны быть однострочными действиями):
            выполнить поиск вложенных вызовов функций, создать для них обёртку в случае наличие вызовов, и простой тривиальный cfg в случае отсутствия вызовов.
        """
        if construct and construct.kind.has('compound'):
            return self.make_cfg_for_compound(construct, wrapped_ast, cfg)

        # Поиск вызовов функций в атомарных узлах
        cfg_name = "atom_" + (construct.name if construct else 'unknown')
        if isinstance(wrapped_ast.ast_node, dict):
            function_calls = self._find_function_calls_in_ast(wrapped_ast.ast_node)
        else:
            function_calls = ()

        if function_calls:
            # Create empty (not connected) CFG
            cfg = CFG(cfg_name)
            # Fill CFG with the chain of func calls
            cfg = self._process_function_calls_in_cfg(cfg, function_calls)
        else:
            # Create connected trivial CFG
            cfg = self._create_simple_cfg(cfg_name)
        return cfg


    def make_cfg_for_compound(self, construct: ConstructSpec, wrapped_ast: ASTNodeWrapper, cfg: CFG = None) -> CFG:
        """ Предполагается, что CFG для подчинённых узлов будут созданы рекурсивно и встроены в результат.
        Если `cfg` передан, то будет использован для наполнения, иначе создан новый.
        """
        if not cfg:
            # Make fresh CFG.
            ast_node = wrapped_ast.ast_node
            cfg_name = ast_node['type'] if 'type' in ast_node else str(ast_node)
            cfg = CFG(cfg_name)

        # Добавить метаданные: алгоритмическая конструкция и узел AST
        cfg.begin_node.metadata.abstract_action = construct.id2action[BEGIN]
        cfg.begin_node.metadata.wrapped_ast = wrapped_ast
        cfg.end_node.metadata.abstract_action = construct.id2action[END]
        cfg.end_node.metadata.wrapped_ast = wrapped_ast

        # Применить все переходы, попутно создавая узлы,
        # c учётом множественности и повторения ...

        unprocessed_pool = [cfg.begin_node]
        processed_ids = set()

        while unprocessed_pool:
            node = unprocessed_pool.pop(0)
            if node.id in processed_ids:
                continue
            processed_ids.add(node.id)

            role = node.role
            # Построить выходящие переходы
            action = construct.id2action.get(role)
            if not action:
                print(f'Warning: no action found for role {role} in construct {construct.name}')
                continue
            outgoing_transitions = construct.find_transitions_from_action(action)
            if not outgoing_transitions:
                # no outgoing transitions: ensure it's END
                assert role == END, f'{construct.name=} has no outgoing transitions for {role=}, and this is not END'
            for tr in outgoing_transitions:
                # resolve target action
                try:
                    step_further_tuple = construct.find_target_action_for_transition(
                        tr, wrapped_ast,
                        node.metadata.wrapped_ast)
                except ValueError as e:
                    print(f'Warning: could not resolve transition {tr.from_} -> {tr.to} (or {tr.to_when_absent})')
                    print(f'  Action: {action.role}, AST: {wrapped_ast.describe()}')
                    print(f'  Error: {e!r}')
                    continue

                target_action, next_wrapped_ast, is_primary, transition_chain = step_further_tuple

                ### DEBUG.
                if 0:
                    print()
                    print(f'{action = }')
                    print(f'{wrapped_ast.ast_node['id'] = }')
                    print(f'previous wrapped_ast->id = {node.metadata.wrapped_ast.ast_node['id']}')
                    print(f'{tr = }')
                    print(f'{target_action = }')
                    print(f'{next_wrapped_ast.ast_node['id'] = }')
                ###

                # Check if node with this role and data already exists
                existing_node = None
                for existing in cfg.nodes.values():
                    if (existing.role == target_action.role and 
                        existing.metadata.wrapped_ast and 
                        existing.metadata.wrapped_ast.ast_node == next_wrapped_ast.ast_node):
                        existing_node = existing
                        break

                if existing_node:
                    node23 = existing_node
                else:
                    # insert subgraph, only for compound actions
                    subgraph = self.make_cfg_for_ast(next_wrapped_ast)

                    node23 = cfg.add_node(
                        kind=target_action.kind,
                        role=target_action.role,
                        metadata=Metadata(
                            abstract_action=target_action,
                            wrapped_ast=next_wrapped_ast,
                            primary=is_primary ,
                        ),
                        subgraph=subgraph
                    )

                # Make a pair: bounds of a compound or an atom (the same node if it's an atom)
                node_pair: tuple[Node, Node] = (node23 if isinstance(node23, tuple) else (node23, node23))

                # connect along the transition found
                cfg.connect(node, node_pair[0], metadata=Metadata(
                    abstract_transition=tr,
                    is_after_last = not is_primary,
                    # transition_chain=transition_chain,  # Could be added to Metadata if needed
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
