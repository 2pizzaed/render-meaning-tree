sequence = [7, 14, 21, 0, 28, 35]
result = 1
for x in sequence:
    if x == 0:
        break
    result = result * x
print(result)