# Вычисление дерева выражения: узел - кортеж (операция, левый, правый), лист - ("num", число)
def evaluate(expr):
    if expr[0] == "num":  # <! FTT >
        return expr[1]
    elif expr[0] == "+":  # <! F >
        left_val = evaluate(expr[1])
        right_val = evaluate(expr[2])
        return left_val + right_val
    elif expr[0] == "*":  # <! T >
        left_val = evaluate(expr[1])  # <! (-, "evaluate(('num', 4))") >
        right_val = evaluate(expr[2])  # <! (-, "evaluate(('num', 7))") >
        return left_val * right_val
    else:
        return 0


# 4 * 7
expr = ("*", ("num", 4), ("num", 7))
print(evaluate(expr))  # <! (-, "evaluate(('*', ('num', 4), ('num', 7)))") >
