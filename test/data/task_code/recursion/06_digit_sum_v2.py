# Сумма цифр числа
def digit_sum(n):
    if n == 0:  # <! FFT >
        return 0
    summ = digit_sum(n // 10)  # <! (-, "digit_sum(9)"), (-, "digit_sum(0)") >
    return n % 10 + summ

num = 98
result = digit_sum(num)  # <! (-, "digit_sum(98)") >
print("digit sum:", result)
