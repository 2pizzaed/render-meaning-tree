# Есть ли у числа делитель: рекурсивный перебор до корня
def has_divisor(n, d):
    if d * d > n:  # <! FF >
        return False
    if n % d == 0:  # <! FT >
        return True
    return has_divisor(n, d + 1)  # <! (-, "has_divisor(9, 3)") >

number = 9
print(has_divisor(number, 2))  # <! (-, "has_divisor(9, 2)") >
