# Умножение через сложение
def multiply(a, b):
    if b == 0:
        return 0
    elif b < 0:
        product = multiply(a, -b)
        return -product
    else:
        product = multiply(a, b - 1)
        return a + product

result = multiply(8, 3)
print("8 * 3 =", result)
