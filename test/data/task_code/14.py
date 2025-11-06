def f(n):
    print("f", n, end=" ")
    return n * 2 if n % 2 else n - 1


def g(n):
    print("g", n, end=" ")
    if n > 2:
        return f(n - 1)
    return n + 1


y = g(4)
print(y)
