# Калькулятор: match выбирает операцию, неизвестная попадает в case _
def calc(a, op, b):
    match op:
        case "+":  # <! FF >
            return a + b
        case "-":  # <! FF >
            return a - b
        case "*":  # <! TF >
            return a * b
        case _:
            return None

print(calc(6, "*", 7))  # <! (-, "calc(6, '*', 7)") >
print(calc(1, "/", 2))  # <! (-, "calc(1, '/', 2)") >
