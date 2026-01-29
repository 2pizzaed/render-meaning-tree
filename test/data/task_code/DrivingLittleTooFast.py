speed = 81
isBirthday = False

allowance = 5 if isBirthday else 0
if speed <= 60 + allowance:
    result = 0
if speed <= 80 + allowance:
    result = 1
result = 2