def fact(n):
    res = 1
    for i in range(2, n + 1):
        res *= i
    return res


y = fact(5)
print("fact(5) =", y)
