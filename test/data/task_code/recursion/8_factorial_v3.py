
def fact(n):
    if n <= 1:  # <! FFT >
        return 1
    else:
        factorial = fact(n - 1)  # <! (-, "fact(2)"), (-, "fact(1)") >
        return n * factorial

n = 3
y = fact(n)  # <! (-, "fact(3)") >
print("fact:", y)
