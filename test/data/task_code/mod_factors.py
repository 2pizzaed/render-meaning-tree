n = 15
if n % 2 == 0:
    if n % 4 == 0:
        if n % 8 == 0:
            code = 3
        else:
            code = 2
    else:
        code = 1
else:
    if n % 3 == 0:
        if n % 9 == 0:
            code = 6
        else:
            code = 5
    else:
        if n % 5 == 0:
            code = 7
        else:
            code = 0
print(code)
