
def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)

y = fact(6)
print("fact(6) =", y)

