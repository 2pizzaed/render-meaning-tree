def fib(n):
    if n <= 2:  # <! FTT >
        return 1
    return fib(n - 1) + fib(n - 2)  # <! fib#1: (-, "fib(2)") > <! fib#2: (-, "fib(1)") >


n = 3
x = fib(n)  # <! (-, "fib(3)") >
print("fib:", x)
