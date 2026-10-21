# Возведение в степень
def power(base, exp):
    if exp == 0:  # <! FFFT >
        return 1
    return base * power(base, exp - 1)  # <! (-, "power(2, 2)"), (-, "power(2, 1)"), (-, "power(2, 0)") >

base = 2
exp = 3
result = power(base, exp)  # <! (-, "power(2, 3)") >
print("power:", result)
