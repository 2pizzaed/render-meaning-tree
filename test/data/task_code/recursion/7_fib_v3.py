def fib(n):
    if n <= 2:
        return n
    else:
        fib1 = fib(n - 1)
        fib2 = fib(n - 2)
        return fib1 + fib2


x = fib(6)
print("fib(6) =", x)
