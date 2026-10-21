# Сумма чисел от 1 до n
def sum_to_n(n):
    if n <= 0:  # <! FFFFT >
        return 0
    return n + sum_to_n(n - 1)  # <! (-, "sum_to_n(3)"), (-, "sum_to_n(2)"), (-, "sum_to_n(1)"), (-, "sum_to_n(0)") >

n = 4
result = sum_to_n(n)  # <! (-, "sum_to_n(4)") >
print("sum:", result)
