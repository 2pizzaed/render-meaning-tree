# Умножение через сложение
def multiply(a, b):
    if b == 0:
        return 0
    if b < 0:
        return -multiply(a, -b)
    return a + multiply(a, b - 1)

result = multiply(7, 6)
print("7 * 6 =", result)
