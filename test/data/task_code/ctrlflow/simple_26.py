data = [2, 4, 6, 8]
i = 0
product = 1

while i < 4:
    if data[i] > 3:
        product = product * data[i]
    i = i + 1

print(product)