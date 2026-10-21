# Вычисление дерева выражения: узел - кортеж (операция, левый, правый), лист - ("num", число)
def evaluate(expr):
    if expr[0] == "num":  # <! FTT >
        return expr[1]
    elif expr[0] == "+":  # <! F >
        left_val = evaluate(expr[1])
        right_val = evaluate(expr[2])
        return left_val + right_val
    elif expr[0] == "*":  # <! T >
        left_val = evaluate(expr[1])  # <! (-, "evaluate(('num', 6))") >
        right_val = evaluate(expr[2])  # <! (-, "evaluate(('num', 2))") >
        return left_val * right_val
    return 0


# 6 * 2
expr = ("*", ("num", 6), ("num", 2))
print(evaluate(expr))  # <! (-, "evaluate(('*', ('num', 6), ('num', 2)))") >
