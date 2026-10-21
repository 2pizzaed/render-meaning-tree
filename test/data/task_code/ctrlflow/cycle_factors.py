numbers = [12, 150, 20, 9, 18, 25]
count_a = 0
count_b = 0
count_c = 0
for n in numbers:
    if n % 3 == 0:
        if n % 5 == 0:
            count_a = count_a + 1
        else:
            count_b = count_b + 1
    else:
        if n % 5 == 0:
            count_b = count_b + 1
        else:
            count_c = count_c + 1
print(count_a, count_b, count_c)
