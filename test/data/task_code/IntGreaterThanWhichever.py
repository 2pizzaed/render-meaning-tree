a = 19
b = 22

if a > 21:
    result = 0 if b > 21 else b
if b > 21:
    result = a
result = max(a, b)