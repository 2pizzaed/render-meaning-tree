numbers = [15, 8, 22, 11, 5, 18, 30, 7, 25, 12]
found = 0
sum_val = 0
for n in numbers:
    if found == 0:
        sum_val = sum_val + n
        if sum_val > 50:
            if n > 15:
                found = 1
            else:
                sum_val = sum_val - n // 2
    else:
        if n % 2 == 0:
            sum_val = sum_val + n
print(sum_val)
