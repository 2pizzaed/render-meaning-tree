# Число шагов гипотезы Коллатца до единицы
def collatz_steps(n):
    if n == 1:  # <! FFT >
        return 0
    if n % 2 == 0:  # <! TT >
        return 1 + collatz_steps(n // 2)  # <! (-, "collatz_steps(2)"), (-, "collatz_steps(1)") >
    return 1 + collatz_steps(3 * n + 1)

print(collatz_steps(4))  # <! (-, "collatz_steps(4)") >
