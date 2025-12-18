# Умножение через сложение
def multiply(a, b):
    if b == 0:
        return 0
    if b < 0:
        return -multiply(a, -b)
    return a + multiply(a, b - 1)

result = multiply(8, 3)
print("8 * 3 =", result)

