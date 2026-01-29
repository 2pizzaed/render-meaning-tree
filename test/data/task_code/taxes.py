income = 80000
children = 2
disabled = 0
if income < 50000:
    base_tax = income * 10 // 100
else:
    if income < 100000:
        base_tax = 5000 + (income - 50000) * 15 // 100
    else:
        base_tax = 12500 + (income - 100000) * 20 // 100
if children > 0:
    if children == 1:
        deduction = 2000
    else:
        if children == 2:
            deduction = 5000
        else:
            deduction = 5000 + (children - 2) * 3000
else:
    deduction = 0
if disabled == 1:
    deduction = deduction + 3000
tax = base_tax - deduction
if tax < 0:
    tax = 0
print(tax)
