numbers = [5, 8, 12, 3, 15, 20, 7]
threshold = 10
found = 0
for n in numbers:
    if n > threshold:
        found = n
        break
print(found)
