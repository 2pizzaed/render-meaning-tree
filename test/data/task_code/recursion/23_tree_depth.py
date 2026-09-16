# Глубина вложенного списка (как дерева)
def tree_depth(node):
    if not isinstance(node, list):
        return 0
    if len(node) == 0:
        return 1
    max_child = 0
    for child in node:
        d = tree_depth(child)
        if d > max_child:
            max_child = d
    return 1 + max_child

tree = [1, [2, [3, 4]], [5]]
depth = tree_depth(tree)
print("tree depth:", depth)
