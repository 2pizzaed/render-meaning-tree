def recurse_f(x):
    print('in')
    if x > 1 and x % 3 == 0:  # <! TFF >
        recurse_f(x - 1)  # <! (-, "recurse_f(2)") >
    if x > 1 and x % 3 == 2:  # <! TFF >
        recurse_f(x - 2)  # <! (-, "recurse_f(0)") >
    print('out')

value = 3
recurse_f(value)  # <! (-, "recurse_f(3)") >
