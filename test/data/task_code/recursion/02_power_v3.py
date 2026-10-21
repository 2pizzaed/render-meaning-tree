# Возведение в степень
def power(base, exp):
    if exp == 0:  # <! FFT >
        return 1
    else:
        power_result = power(base, exp - 1)  # <! (-, "power(5, 1)"), (-, "power(5, 0)") >
        return base * power_result

base = 5
exp = 2
result = power(base, exp)  # <! (-, "power(5, 2)") >
print("power:", result)
