def fib(n):
    if n <= 2:
        return n
    return fib(n - 1) + fib(n - 2)


x = fib(4)
print("fib(4) =", x)

