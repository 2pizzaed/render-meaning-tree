# Умножение через сложение
def multiply(a, b):
    if b == 0:  # <! FFFT >
        return 0
    if b < 0:  # <! TFF >
        return -multiply(a, -b)  # <! (-, "multiply(4, 2)") >
    return a + multiply(a, b - 1)  # <! (-, "multiply(4, 1)"), (-, "multiply(4, 0)") >

a = 4
b = -2
result = multiply(a, b)  # <! (-, "multiply(4, -2)") >
print("product:", result)
