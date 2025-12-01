def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)


x = fib(6)
print("fib(6) =", x)
