def recurse_sum(x):
    if x <= 1:
        return x
    if x % 2 == 0:
        return x + recurse_sum(x - 1)
    else:
        return recurse_sum(x - 1) - x

value = 5
r1 = recurse_sum(value)