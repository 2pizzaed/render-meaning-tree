# Умножение через сложение
def multiply(a, b):
    if b == 0:  # <! FFT >
        return 0
    elif b < 0:  # <! TF >
        product = multiply(a, -b)  # <! (-, "multiply(3, 1)") >
        return -product
    else:
        product = multiply(a, b - 1)  # <! (-, "multiply(3, 0)") >
        return a + product

a = 3
b = -1
result = multiply(a, b)  # <! (-, "multiply(3, -1)") >
print("product:", result)
