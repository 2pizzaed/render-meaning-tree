# Умножение через сложение
def multiply(a, b):
    if b == 0:  # <! FFT >
        return 0
    if b < 0:  # <! FF >
        product = multiply(a, -b)
        return -product
    product = multiply(a, b - 1)  # <! (-, "multiply(5, 1)"), (-, "multiply(5, 0)") >
    return a + product

a = 5
b = 2
result = multiply(a, b)  # <! (-, "multiply(5, 2)") >
print("product:", result)
