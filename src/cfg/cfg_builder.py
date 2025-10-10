from typing import Optional

from src.cfg.abstractions import ConstructSpec
from src.cfg.ast_wrapper import ASTNodeWrapper
from src.cfg.cfg import Node, CFG, BEGIN, END, Metadata


# ---------- CFGBuilder ----------
class CFGBuilder:
    def __init__(self, constructs_map: dict[str, ConstructSpec]):
        self.constructs = constructs_map

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

    def make_cfg_for_ast(self, wrapped_ast: ASTNodeWrapper) -> CFG:
        construct = self.find_construct_for_astnode(wrapped_ast)
        if construct:
            return self.make_cfg_for_construct(construct, wrapped_ast)
        # fallback empty
        cfg = CFG("atom")
        cfg.connect(cfg.begin_node, cfg.end_node)
        return cfg

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
                    target_action_data_primary = construct.find_target_action_for_transition(
                        tr, wrapped_ast,
                        node.metadata.wrapped_ast)
                except ValueError as e:
                    print(f'Warning: could not resolve transition {tr.from_} -> {tr.to} (or {tr.to_when_absent})')
                    print(f'  Action: {action.role}, AST: {wrapped_ast.describe()}')
                    print(f'  Error: {e}')
                    continue

                target_action, next_wrapped_ast, primary, transition_chain = target_action_data_primary

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
                    if target_action.kind == 'compound':
                        subgraph = self.make_cfg_for_ast(next_wrapped_ast)
                    else:
                        subgraph = None

                    node23 = cfg.add_node(
                        kind=target_action.kind,
                        role=target_action.role,
                        metadata=Metadata(
                            abstract_action=target_action,
                            wrapped_ast=next_wrapped_ast,
                            primary=primary ,
                        ),
                        subgraph=subgraph
                    )

                # Make a pair: bounds of a compound or an atom (the same node if it's an atom)
                node_pair: tuple[Node, Node] = (node23 if isinstance(node23, tuple) else (node23, node23))

                # connect along the transition found
                cfg.connect(node, node_pair[0], metadata=Metadata(
                    abstract_transition=tr,
                    is_after_last = not primary,
                    # transition_chain=transition_chain,  # Could be added to Metadata if needed
                ))

                # последний узел (выходной) добавить в пул необработанных
                next_node = node_pair[1]
                if next_node.id not in processed_ids:
                    unprocessed_pool.append(next_node)
            # end of for.
        return cfg
