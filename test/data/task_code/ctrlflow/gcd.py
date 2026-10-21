i, j = 5, 7
a = i
b = j
while b != 0:
    temp = a % b
    a = b
    b = temp
result = a
print((i * j) // result)