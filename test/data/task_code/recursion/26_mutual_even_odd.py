# Взаимная рекурсия: чётность/нечётность
def is_even(n):
    if n == 0:
        return True
    return is_odd(n - 1)

def is_odd(n):
    if n == 0:
        return False
    return is_even(n - 1)

num = 7
print(f"{num} is even:", is_even(num))
print(f"{num} is odd:", is_odd(num))
