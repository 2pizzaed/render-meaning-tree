# Сумма чисел от 1 до n
def sum_to_n(n):
    if n <= 0:  # <! FFT >
        return 0
    else:
        summ = sum_to_n(n - 1)  # <! (-, "sum_to_n(1)"), (-, "sum_to_n(0)") >
        return n + summ

n = 2
result = sum_to_n(n)  # <! (-, "sum_to_n(2)") >
print("sum:", result)
