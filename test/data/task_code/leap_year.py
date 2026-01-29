year = 2024
month = 2
day = 15
if year % 400 == 0:
    leap = 1
else:
    if year % 100 == 0:
        leap = 0
    else:
        if year % 4 == 0:
            leap = 1
        else:
            leap = 0
if month == 2:
    if leap == 1:
        days = 29
    else:
        days = 28
else:
    days = 30
result = days - day
print(result)
