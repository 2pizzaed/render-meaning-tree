a = 7
b = 3
c = 10

result = 0

if a > b:
    if a > c:
        result = a
    else:
        result = c
else:
    if b > c:
        result = b
    else:
        result = c

print(result)
