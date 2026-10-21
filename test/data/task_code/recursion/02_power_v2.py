# Возведение в степень
def power(base, exp):
    if exp == 0:  # <! FFT >
        return 1
    power_result = power(base, exp - 1)  # <! (-, "power(3, 1)"), (-, "power(3, 0)") >
    return base * power_result

base = 3
exp = 2
result = power(base, exp)  # <! (-, "power(3, 2)") >
print("power:", result)
