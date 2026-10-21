arr1 = [2, 4, 6]
arr2 = [3, 7]
product = 1
for x in arr1:
    for y in arr2:
        if x + y > 10:
            if x * y < 20:
                product = product * 2
            else:
                product = product + x
        else:
            if y % 2 == 1:
                product = product + y
print(product)
