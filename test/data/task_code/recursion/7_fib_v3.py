def fib(n):
    if n <= 1:  # <! FTT >
        return n
    else:
        fib1 = fib(n - 1)  # <! (-, "fib(1)") >
        fib2 = fib(n - 2)  # <! (-, "fib(0)") >
        return fib1 + fib2


n = 2
x = fib(n)  # <! (-, "fib(2)") >
print("fib:", x)
