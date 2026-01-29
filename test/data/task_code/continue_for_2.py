arr = [3, 8, 15, 10, 7, 12, 5, 20]
count = 0
for num in arr:
    if num % 2 != 0:
        continue
    count = count + 1
print(count)