list1 = [10, 5, 15, 8]
list2 = [12, 7, 20, 3]
pair_found = 0
for a in list1:
    for b in list2:
        if a + b > 25:
            pair_found = a + b
            break
    if pair_found > 0:
        break
print(pair_found)
