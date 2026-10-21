nums = [1, 2, 2, 1]

total = 0
skip_next = False
for x in nums:
    if x == 13:
        skip_next = True
        continue
    if skip_next:
        skip_next = False
        continue
    total += x
result = total