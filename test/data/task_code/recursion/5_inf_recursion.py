def recurse_f(x):
    print('in')
    if x > 1:  # <! TTF >
        recurse_f(x - 1)  # <! (-, "recurse_f(2)"), (-, "recurse_f(1)") >
    print('out')

value = 3
recurse_f(value)  # <! (-, "recurse_f(3)") >
