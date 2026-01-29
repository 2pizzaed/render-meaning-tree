nums = [2, 10, 3, 4, 20, 5]

out = nums[:]
running = None
for i in range(len(out)):
    if out[i] % 10 == 0:
        running = out[i]
    elif running is not None:
        out[i] = running
result = out