def fib_dyn(n):
    res = 1
    for i in range(2, n + 1):
        res *= i
    return res

def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)

y = fact(5)
print("fact(5) =", y)
