# Переворот числа: накопитель передаётся через параметр по умолчанию
def reverse_num(n, acc=0):
    if n == 0:  # <! FFT >
        return acc
    return reverse_num(n // 10, acc * 10 + n % 10)  # <! (-, "reverse_num(1, 2)"), (-, "reverse_num(0, 21)") >

number = 12
print(reverse_num(number))  # <! (-, "reverse_num(12, 0)") >
