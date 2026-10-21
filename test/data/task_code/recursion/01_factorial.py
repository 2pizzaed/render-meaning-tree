def fact(n):
    if n <= 1:  # <! FFT >
        return 1
    return n * fact(n - 1)  # <! (-, "fact(2)"), (-, "fact(1)") >

n = 3
print(fact(n))  # <! (-, "fact(3)") >
