price = 1000
quantity = 5
vip = 1
if vip == 1:
    if quantity > 10:
        discount = 30
    else:
        if quantity > 5:
            discount = 20
        else:
            discount = 15
else:
    if quantity > 10:
        discount = 15
    else:
        if quantity > 5:
            discount = 10
        else:
            discount = 0
total = price * quantity * (100 - discount) // 100
print(total)
