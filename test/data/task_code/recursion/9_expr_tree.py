# Вычисление дерева выражения: узел - кортеж (операция, левый, правый), лист - ("num", число)
def evaluate(expr):
    if expr[0] == "num":  # <! FTT >
        return expr[1]
    elif expr[0] == "+":  # <! F >
        return evaluate(expr[1]) + evaluate(expr[2])
    elif expr[0] == "*":  # <! T >
        return evaluate(expr[1]) * evaluate(expr[2])  # <! evaluate#1: (-, "evaluate(('num', 3))") > <! evaluate#2: (-, "evaluate(('num', 4))") >
    return 0


# 3 * 4
expr = ("*", ("num", 3), ("num", 4))
print(evaluate(expr))  # <! (-, "evaluate(('*', ('num', 3), ('num', 4)))") >
