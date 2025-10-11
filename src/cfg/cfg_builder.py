from typing import Optional

from src.cfg.abstractions import ConstructSpec
from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.cfg import Node, CFG, BEGIN, END, Metadata


FUNC_DEF_CONSTRUCT = 'func_def_structure'
FUNC_CALL_CONSTRUCT = 'func_call_structure'


# ---------- CFGBuilder ----------
class CFGBuilder:
    constructs: dict[str, ConstructSpec]
    func_cfgs: dict[str, CFG]

    def __init__(self, constructs_map: dict[str, ConstructSpec]):
        self.constructs = constructs_map
        self.func_cfgs = {}

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

    def _handle_function_definition(self, construct: ConstructSpec, wrapped_ast: ASTNodeWrapper) -> CFG:
        """Обрабатывает определение функции: создает CFG для тела функции и сохраняет в func_cfgs."""
        # Извлекаем имя функции
        func_name = self._extract_function_name(wrapped_ast, construct)
        if not func_name:
            print(f'Warning: could not extract function name, skipping function definition')
            # Возвращаем пустой CFG
            cfg = CFG("empty_function_def")
            cfg.connect(cfg.begin_node, cfg.end_node)
            return cfg
        
        # Создаем CFG для тела функции
        func_body_cfg = self.make_cfg_for_construct(construct, wrapped_ast)
        
        # Сохраняем CFG функции в словаре
        self.func_cfgs[func_name] = func_body_cfg
        
        # Возвращаем пустой CFG (чтобы определение не попало в основной поток)
        cfg = CFG("function_definition")
        cfg.connect(cfg.begin_node, cfg.end_node)
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
            # Обрабатываем как обычный compound без call stack эффектов
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
            kind='compound',
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
            is_after_last=False,
        ))
        
        # func -> END (с эффектом drop_frame)
        func_to_end_transition = construct.find_transitions_from_action(construct.id2action['func'])[0]
        call_cfg.connect(func_node_pair[1], call_cfg.end_node, metadata=Metadata(
            abstract_transition=func_to_end_transition,
            is_after_last=False,
        ))
        
        return call_cfg

    def make_cfg_for_ast(self, wrapped_ast: ASTNodeWrapper) -> CFG | None:
        """
        Make CFG for AST node.
        Args:
            wrapped_ast:

        Returns:
            CFG for a compound node or None for an atom.
        """
        construct = self.find_construct_for_astnode(wrapped_ast)
        if construct:
            # Проверяем специальные случаи для функций
            if construct.name == FUNC_DEF_CONSTRUCT:
                return self._handle_function_definition(construct, wrapped_ast)
            elif construct.name == FUNC_CALL_CONSTRUCT:
                return self._handle_function_call(construct, wrapped_ast)
            # Обычные узлы
            if construct.kind != 'atom':
                return self.make_cfg_for_construct(construct, wrapped_ast)
            else:
                cfg = CFG("atom_" + construct.name)
                cfg.connect(cfg.begin_node, cfg.end_node)
                # cfg.begin_node.metadata.abstract_action = construct.id2action['atom']
                return cfg
        # fallback: unknown construct.
        return None

    def make_cfg_for_construct(self, construct: ConstructSpec, wrapped_ast: ASTNodeWrapper) -> CFG:
        """ Предполагается, что CFG для подчинённых узлов уже подготовлены и готовы быть встроены в новый. -- будут созданы рекурсивно. """
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
