a = 8
b = 3
c = 5
if a >= b:
    if a >= c:
        max_val = a
        if b >= c:
            mid_val = b
            min_val = c
        else:
            mid_val = c
            min_val = b
    else:
        max_val = c
        mid_val = a
        min_val = b
else:
    if b >= c:
        max_val = b
        if a >= c:
            mid_val = a
            min_val = c
        else:
            mid_val = c
            min_val = a
    else:
        max_val = c
        mid_val = b
        min_val = a
result = max_val + mid_val
print(result)
