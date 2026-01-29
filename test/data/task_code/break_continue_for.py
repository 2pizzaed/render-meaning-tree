values = [6, 11, 9, 14, 12, 17, 15, 19]
sum_val = 0
for v in values:
    if v % 3 == 0:
        continue
    sum_val = sum_val + v
    if sum_val > 40:
        break
print(sum_val)
