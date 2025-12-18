# Вывод чисел от n до 1 и обратно
def print_down_up(n):
    if n <= 0:
        return
    print("down:", n)
    print_down_up(n - 1)
    print("up:", n)

print_down_up(3)
