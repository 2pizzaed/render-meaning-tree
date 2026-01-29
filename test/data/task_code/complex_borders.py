arr = [5, 3, 8]
result = 0
index = 0
for val in arr:
    if index == 0:
        if val > 4:
            result = result + val * 2
        else:
            result = result + val
    else:
        if index == 1:
            if val < 4:
                result = result + val * 3
            else:
                result = result - val
        else:
            if val > 6:
                result = result + val
            else:
                result = result + 1
    index = index + 1
print(result)
