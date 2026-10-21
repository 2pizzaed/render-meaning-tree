# Взаимная рекурсия: чётность/нечётность
def is_even(n):
    if n == 0:  # <! FF >
        return True
    return is_odd(n - 1)  # <! (-, "is_odd(2)"), (-, "is_odd(0)") >

def is_odd(n):
    if n == 0:  # <! FT >
        return False
    return is_even(n - 1)  # <! (-, "is_even(1)") >

num = 3
result = is_even(num)  # <! (-, "is_even(3)") >
print("even:", result)
