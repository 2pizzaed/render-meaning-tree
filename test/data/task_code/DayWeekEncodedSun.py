day = 0
vacation = False

if vacation:
    if 1 <= day <= 5:
        result = "10:00"
    else:
        result = "off"
else:
    if 1 <= day <= 5:
        result = "7:00"
    else:
        result = "10:00"