nums = [2, 4, 6, 8, 7, 10, 12]
valid = 1
prev = 0
for n in nums:
    if n <= prev:
        valid = 0
        break
    prev = n
print(valid, prev)
