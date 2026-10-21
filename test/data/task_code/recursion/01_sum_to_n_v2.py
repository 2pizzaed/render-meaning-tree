# Сумма чисел от 1 до n
def sum_to_n(n):
    if n <= 0:  # <! FFFT >
        return 0
    summ = sum_to_n(n - 1)  # <! (-, "sum_to_n(2)"), (-, "sum_to_n(1)"), (-, "sum_to_n(0)") >
    return n + summ

n = 3
result = sum_to_n(n)  # <! (-, "sum_to_n(3)") >
print("sum:", result)
