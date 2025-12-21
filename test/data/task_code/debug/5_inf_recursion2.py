def recurse_f(x):
    print('in')
    if x > 1 and x % 3 > 0:
        recurse_f(x - 1)
    if x > 1 and x % 3 < 2:
        recurse_f(x - 2)
    print('out')

value = 5
r1 = recurse_f(value)
value = 7
