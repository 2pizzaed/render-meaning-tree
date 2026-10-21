# Глубина вложенного списка (как дерева)
def tree_depth(node):
    if not isinstance(node, list):  # <! FF >
        return 0
    max_child = 0
    for child in node:  # <! TFF >
        d = tree_depth(child)  # <! (-, "tree_depth([])") >
        if d > max_child:  # <! T >
            max_child = d
    return 1 + max_child

tree = [[]]
depth = tree_depth(tree)  # <! (-, "tree_depth([[]])") >
print("depth:", depth)
