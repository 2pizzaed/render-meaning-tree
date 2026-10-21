# Вывод чисел от n до 1 и обратно
def print_down_up(n):
    if n <= 0:  # <! FFT >
        return
    print("down:", n)
    print_down_up(n - 1)  # <! (-, "print_down_up(1)"), (-, "print_down_up(0)") >
    print("up:", n)

n = 2
print_down_up(n)  # <! (-, "print_down_up(2)") >
