def recurse_f(x):
    print('in')
    if rand() > 0.5:
        recurse_f(x - 1)
    if rand() < 0.5:
        recurse_f(x + 2)
    print('out')

value = 5
r1 = recurse_f(value)
value = 7
