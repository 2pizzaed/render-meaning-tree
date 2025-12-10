def recurse_f(x):
    print('in')
    if rand() > 0.5:
        recurse_f(x - 1)
    print('out')

value = 5
r1 = recurse_f(value)
