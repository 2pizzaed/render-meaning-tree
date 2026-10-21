# Повторение строки n раз рекурсией
def repeat(s, n):
    if n == 0:  # <! FFT >
        return ""
    return s + repeat(s, n - 1)  # <! (-, "repeat('ха', 1)"), (-, "repeat('ха', 0)") >

times = 2
print(repeat("ха", times))  # <! (-, "repeat('ха', 2)") >
