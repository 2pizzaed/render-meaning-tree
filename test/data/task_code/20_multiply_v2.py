# Умножение через сложение
def multiply(a, b):
    if b == 0:
        return 0
    if b < 0:
        product = multiply(a, -b)
        return -product
    product = multiply(a, b - 1)
    return a + product

result = multiply(5, 4)
print("5 * 4 =", result)
