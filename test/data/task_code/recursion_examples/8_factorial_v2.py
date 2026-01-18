
def fact(n):
    if n <= 1:
        return 1
    factorial = fact(n - 1)
    return n * factorial

y = fact(4)
print("fact(4) =", y)
