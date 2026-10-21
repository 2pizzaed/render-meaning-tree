# Двоичная запись числа: старшие разряды получаются из рекурсивного вызова
def to_binary(n):
    if n < 2:  # <! FFT >
        return str(n)
    return to_binary(n // 2) + str(n % 2)  # <! (-, "to_binary(2)"), (-, "to_binary(1)") >

number = 5
print(to_binary(number))  # <! (-, "to_binary(5)") >
