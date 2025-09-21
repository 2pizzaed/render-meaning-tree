from typing import Dict, List, Set, Optional, Any, Tuple, Callable, cast
import networkx as nx
import matplotlib.pyplot as plt
from src.types import Node, NodeType
from src.serializers.serializer import Serializer
from collections import defaultdict, deque


class BasicBlock:
    def __init__(self, block_id: str, ast_nodes=None):
        self.id = block_id
        self.ast_nodes = ast_nodes or []
        self.instructions = []
        self.is_entry = False
        self.is_exit = False

    def __str__(self):
        if self.is_entry:
            return f"ENTRY: {self.id}"
        if self.is_exit:
            return f"EXIT: {self.id}"
        if self.instructions:
            return f"BB-{self.id}: {'; '.join(self.instructions)}"
        return f"BB-{self.id}"

    def __repr__(self):
        return self.__str__()

    def add_instruction(self, instruction: str):
        self.instructions.append(instruction)


class ControlFlowGraph(Serializer):
    def __init__(self):
        super().__init__()
        self.graph = nx.DiGraph()
        self.blocks = {}
        self.entry_block = None
        self.exit_block = None
        self.current_block_id = 0
        
        self.dominators = {}
        self.post_dominators = {}
        self.immediate_dominators = {}
        self.immediate_post_dominators = {}
        self.dominator_tree = nx.DiGraph()
        self.post_dominator_tree = nx.DiGraph()
        
        self.back_edges = set()
        self.critical_edges = set()
        self.abnormal_edges = set()
        self.impossible_edges = set()
        
        self.loops = []
        self.loop_headers = set()

    def _create_block(self) -> BasicBlock:
        self.current_block_id += 1
        block_id = f"block_{self.current_block_id}"
        block = BasicBlock(block_id)
        self.blocks[block_id] = block
        self.graph.add_node(block_id, block=block)
        return block

    def _add_edge(self, source: BasicBlock, target: BasicBlock, edge_type: str = "forward"):
        if source is None or target is None:
            return
            
        self.graph.add_edge(source.id, target.id, type=edge_type)
        
        if self.graph.out_degree(source.id) > 1 and self.graph.in_degree(target.id) > 1:
            self.critical_edges.add((source.id, target.id))

    def generate_cfg(self, ast: Node) -> nx.DiGraph:
        self.graph = nx.DiGraph()
        self.blocks = {}
        self.current_block_id = 0
        self.dominators = {}
        self.post_dominators = {}
        self.immediate_dominators = {}
        self.immediate_post_dominators = {}
        self.dominator_tree = nx.DiGraph()
        self.post_dominator_tree = nx.DiGraph()
        self.back_edges = set()
        self.critical_edges = set()
        self.abnormal_edges = set()
        self.impossible_edges = set()
        self.loops = []
        self.loop_headers = set()
        
        self.entry_block = self._create_block()
        self.entry_block.is_entry = True
        self.exit_block = self._create_block()
        self.exit_block.is_exit = True
        
        self._process_node(ast, self.entry_block, self.exit_block)
        
        self._remove_unreachable_blocks()
        
        self._compute_dominators()
        self._compute_post_dominators()
        
        self._identify_back_edges_and_loops()
        
        self._ensure_exit_block_post_dominates_all()
        
        return self.graph
    
    def _process_node(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
        if node is None or entry_block is None or exit_block is None:
            return entry_block, exit_block
            
        node_type = node.get("type", "")
        
        if node_type in self.serialize_funcs:
            handler = self.serialize_funcs[cast(NodeType, node_type)]
            return handler(self, node, entry_block, exit_block)
        else:
            if entry_block is not None and not entry_block.is_entry: 
                instruction = f"{node_type}"
                entry_block.add_instruction(instruction)
            
            if entry_block is not None and exit_block is not None and entry_block != exit_block:
                self._add_edge(entry_block, exit_block)
                
            return entry_block, exit_block
    
    def _remove_unreachable_blocks(self):
        if self.entry_block is None:
            return
            
        reachable = set(nx.descendants(self.graph, self.entry_block.id))
        reachable.add(self.entry_block.id)
        
        unreachable = set(self.graph.nodes()) - reachable
        for block_id in unreachable:
            self.graph.remove_node(block_id)
            if block_id in self.blocks:
                del self.blocks[block_id]
    
    def _compute_dominators(self):
        if self.entry_block is None:
            return
            
        doms = {}
        all_blocks = set(self.graph.nodes())
        
        doms[self.entry_block.id] = {self.entry_block.id}
        
        for n in all_blocks - {self.entry_block.id}:
            doms[n] = all_blocks.copy()
        
        changed = True
        while changed:
            changed = False
            for n in all_blocks - {self.entry_block.id}:
                new_doms = {n}
                preds = set(self.graph.predecessors(n))
                if preds:
                    pred_doms = [doms[p] for p in preds]
                    if pred_doms:
                        new_doms = new_doms.union(set.intersection(*pred_doms))
                
                if new_doms != doms[n]:
                    doms[n] = new_doms
                    changed = True
        
        self.dominators = doms
        
        for n in all_blocks:
            if n == self.entry_block.id:
                continue
                
            idom = None
            doms_n = doms[n] - {n}
            
            for d in doms_n:
                if all(d not in doms[other_dom] or other_dom == d for other_dom in doms_n - {d}):
                    idom = d
                    break
            
            if idom:
                self.immediate_dominators[n] = idom
                self.dominator_tree.add_edge(idom, n)
    
    def _compute_post_dominators(self):
        if self.exit_block is None:
            return
            
        reversed_graph = self.graph.reverse()
        
        pdoms = {}
        all_blocks = set(reversed_graph.nodes())
        
        pdoms[self.exit_block.id] = {self.exit_block.id}
        
        for n in all_blocks - {self.exit_block.id}:
            pdoms[n] = all_blocks.copy()
        
        changed = True
        while changed:
            changed = False
            for n in all_blocks - {self.exit_block.id}:
                new_pdoms = {n}
                succs = set(reversed_graph.predecessors(n))  # Successors in original graph
                if succs:
                    succ_pdoms = [pdoms[s] for s in succs]
                    if succ_pdoms:
                        new_pdoms = new_pdoms.union(set.intersection(*succ_pdoms))
                
                if new_pdoms != pdoms[n]:
                    pdoms[n] = new_pdoms
                    changed = True
        
        self.post_dominators = pdoms
        
        for n in all_blocks:
            if n == self.exit_block.id:
                continue
                
            ipdom = None
            pdoms_n = pdoms[n] - {n}
            
            for pd in pdoms_n:
                if all(pd not in pdoms[other_pdom] or other_pdom == pd for other_pdom in pdoms_n - {pd}):
                    ipdom = pd
                    break
            
            if ipdom:
                self.immediate_post_dominators[n] = ipdom
                self.post_dominator_tree.add_edge(ipdom, n)
    
    def _identify_back_edges_and_loops(self):
        if self.entry_block is None:
            return
            
        visited = set()
        finished = set()
        
        def dfs(node):
            if node in visited and node not in finished:
                self.back_edges.add((current_path[-1], node))
                if node in self.dominators.get(current_path[-1], set()):
                    
                    self.loop_headers.add(node)
                return
                
            if node in visited:
                return
                
            visited.add(node)
            current_path.append(node)
            
            for succ in self.graph.successors(node):
                dfs(succ)
            
            current_path.pop()
            finished.add(node)
        
        current_path = []
        dfs(self.entry_block.id)
        
        for src, dst in self.back_edges:
            self.graph[src][dst]['type'] = 'back'
    
    def _ensure_exit_block_post_dominates_all(self):
        if self.exit_block is None:
            return
        
        for node in self.graph.nodes():
            if node == self.exit_block.id:
                continue
                
            if not nx.has_path(self.graph, node, self.exit_block.id):
                if node in self.blocks:
                    self._add_edge(self.blocks[node], self.exit_block, edge_type="impossible")
                    self.impossible_edges.add((node, self.exit_block.id))
    
    def is_reducible(self) -> bool:
        for src, dst in self.back_edges:
            if dst not in self.dominators.get(src, set()):
                return False
        
        forward_edges = [(u, v) for u, v, data in self.graph.edges(data=True) 
                        if data.get('type', 'forward') == 'forward']
        forward_graph = nx.DiGraph()
        forward_graph.add_nodes_from(self.graph.nodes())
        forward_graph.add_edges_from(forward_edges)
        
        if not nx.is_directed_acyclic_graph(forward_graph):
            return False
            
        return True
    
    def get_loop_connectedness(self) -> int:
        if not self.back_edges or self.entry_block is None:
            return 0
            
        forward_graph = self.graph.copy()
        for src, dst in self.back_edges:
            forward_graph.remove_edge(src, dst)
        
        max_connectedness = 0
        
        for node in self.graph.nodes():
            if node == self.entry_block.id:
                continue
                
            try:
                for path in nx.all_simple_paths(forward_graph, self.entry_block.id, node):
                    back_edge_sources = set(src for src, dst in self.back_edges if src in path)
                    max_connectedness = max(max_connectedness, len(back_edge_sources))
            except nx.NetworkXNoPath:
                continue
        
        return max_connectedness
    
    def visualize(self, output_file: str = "cfg.png"):
        pos = nx.spring_layout(self.graph, seed=42)
        plt.figure(figsize=(14, 10))
        
        node_labels = {n: str(self.blocks[n]) for n in self.graph.nodes()}
        
        entry_nodes = [n for n, block in self.blocks.items() if block.is_entry]
        exit_nodes = [n for n, block in self.blocks.items() if block.is_exit]
        loop_header_nodes = [n for n in self.loop_headers]
        normal_nodes = [n for n in self.graph.nodes() if n not in entry_nodes and 
                        n not in exit_nodes and n not in loop_header_nodes]
        
        nx.draw_networkx_nodes(self.graph, pos, nodelist=entry_nodes, node_color='green', 
                            node_size=2000, alpha=0.8)
        nx.draw_networkx_nodes(self.graph, pos, nodelist=exit_nodes, node_color='red', 
                            node_size=2000, alpha=0.8)
        nx.draw_networkx_nodes(self.graph, pos, nodelist=loop_header_nodes, node_color='orange', 
                            node_size=2000, alpha=0.8)
        nx.draw_networkx_nodes(self.graph, pos, nodelist=normal_nodes, node_color='skyblue', 
                            node_size=2000, alpha=0.8)
        
        nx.draw_networkx_labels(self.graph, pos, labels=node_labels, font_size=8)
        
        forward_edges = [(u, v) for u, v, data in self.graph.edges(data=True) 
                        if data.get('type', 'forward') == 'forward']
        back_edges = list(self.back_edges)
        critical_edges = list(self.critical_edges)
        impossible_edges = list(self.impossible_edges)
        
        nx.draw_networkx_edges(self.graph, pos, edgelist=forward_edges, 
                              arrows=True, arrowsize=15, edge_color='black')
        
        nx.draw_networkx_edges(self.graph, pos, edgelist=back_edges, 
                              arrows=True, arrowsize=15, edge_color='red', 
                              connectionstyle='arc3,rad=0.3')
        
        nx.draw_networkx_edges(self.graph, pos, edgelist=critical_edges, 
                              arrows=True, arrowsize=15, edge_color='blue')
        
        nx.draw_networkx_edges(self.graph, pos, edgelist=impossible_edges, 
                              arrows=True, arrowsize=15, edge_color='gray', 
                              style='dashed')
        
        plt.figtext(0.01, 0.01, "Green: Entry Block\nRed: Exit Block\nOrange: Loop Header\nBlue: Normal Block", 
                   fontsize=10, bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5})
        plt.figtext(0.3, 0.01, "Black: Forward Edge\nRed: Back Edge\nBlue: Critical Edge\nGray: Impossible Edge", 
                   fontsize=10, bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5})
        
        properties = [
            f"Reducible: {self.is_reducible()}",
            f"Loop Headers: {len(self.loop_headers)}",
            f"Loop Connectedness: {self.get_loop_connectedness()}"
        ]
        plt.figtext(0.6, 0.01, "\n".join(properties), 
                   fontsize=10, bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5})
        
        plt.title("Control Flow Graph")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_file


cfg = ControlFlowGraph()


@cfg.node(type="program_entry_point")
def program_entry_point(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    current_block = entry_block
    
    if "body" in node and isinstance(node["body"], list):
        for stmt in node["body"]:
            stmt_entry, stmt_exit = self._process_node(stmt, current_block, exit_block)
            current_block = stmt_exit
    
    if current_block != exit_block:
        self._add_edge(current_block, exit_block)
        
    return entry_block, exit_block


@cfg.node(type="compound_statement")
def compound_statement(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    current_block = entry_block
    
    if "statements" in node and isinstance(node["statements"], list):
        for stmt in node["statements"]:
            stmt_entry, stmt_exit = self._process_node(stmt, current_block, exit_block)
            current_block = stmt_exit
    
    return entry_block, current_block


@cfg.node(type="if_statement")
def if_statement(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    if entry_block.is_entry:
        condition_block = self._create_block()
        self._add_edge(entry_block, condition_block)
    else:
        condition_block = entry_block
    
    condition_block.add_instruction("if condition")
    
    after_if_block = self._create_block()
    
    if "branches" in node and isinstance(node["branches"], list):
        branch_exit_blocks = []
        
        for i, branch in enumerate(node["branches"]):
            branch_block = self._create_block()
            
            self._add_edge(condition_block, branch_block)
            
            _, branch_exit = self._process_node(branch["body"], branch_block, after_if_block)
            
            if branch_exit != after_if_block:
                self._add_edge(branch_exit, after_if_block)
                
            branch_exit_blocks.append(branch_exit)
    
    return entry_block, after_if_block


@cfg.node(type="while_loop")
def while_loop(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    loop_header = self._create_block()
    loop_header.add_instruction("while condition")
    
    after_loop = self._create_block()
    
    if entry_block != loop_header:
        self._add_edge(entry_block, loop_header)
    
    if "body" in node:
        loop_body = self._create_block()
        self._add_edge(loop_header, loop_body, "true") 
        
        _, body_exit = self._process_node(node["body"], loop_body, loop_header)
        
        if body_exit != loop_header:
            self._add_edge(body_exit, loop_header, "back")
    
    self._add_edge(loop_header, after_loop, "false")
    
    return entry_block, after_loop


@cfg.node(type="range_for_loop")
def for_loop(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    init_block = self._create_block()
    init_block.add_instruction(f"for init: {node.get('identifier', '')}")
    
    cond_block = self._create_block()
    cond_block.add_instruction("for condition")
    
    incr_block = self._create_block()
    incr_block.add_instruction("for increment")
    
    after_loop = self._create_block()
    
    self._add_edge(entry_block, init_block)
    self._add_edge(init_block, cond_block)
    
    if "body" in node:
        body_block = self._create_block()
        self._add_edge(cond_block, body_block, "true")
        
        _, body_exit = self._process_node(node["body"], body_block, incr_block)
        
        if body_exit != incr_block:
            self._add_edge(body_exit, incr_block)
    
    self._add_edge(incr_block, cond_block, "back")
    
    self._add_edge(cond_block, after_loop, "false")
    
    return entry_block, after_loop


@cfg.node(type="assignment_statement")
def assignment_statement(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    if "target" in node and "value" in node:
        target = node.get("target", {}).get("name", "var")
        content = f"{target} = expression"
    else:
        content = "assignment"
    
    if entry_block is not None and not entry_block.is_entry:  
        entry_block.add_instruction(content)
    
    return entry_block, entry_block


def generate_cfg_from_tree(ast: Node) -> nx.DiGraph:
    return cfg.generate_cfg(ast) 