def recurse_sum(x):
    if x <= 1:  # <! FFT >
        return x
    if x % 2 == 0:  # <! FT >
        return x + recurse_sum(x - 1)  # <! (-, "recurse_sum(1)") >
    else:
        return recurse_sum(x - 1) - x  # <! (-, "recurse_sum(2)") >

value = 3
r1 = recurse_sum(value)  # <! (-, "recurse_sum(3)") >
print(r1)
