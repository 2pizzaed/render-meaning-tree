values = [8, 15, 3, 22, 9]
total = 0
bonus = 0
for v in values:
    total = total + v
    if total > 50:
        if v > 10:
            bonus = bonus + v // 2
        else:
            bonus = bonus + v
    else:
        if v > 15:
            bonus = bonus + 5
print(total, bonus)
