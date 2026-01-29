n = 30
i = 1
result = 0
while i < n:
    if i % 3 == 0:
        if i % 2 == 0:
            result = result + i
            i = i + 1
        else:
            result = result - i
            i = i + 2
    else:
        if i > 10:
            i = i + 3
        else:
            i = i + 1
print(result)
