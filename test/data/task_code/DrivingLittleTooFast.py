speed = 81
isBirthday = False

allowance = 5 if isBirthday else 0
if speed <= 60 + allowance:
    print(0)
elif speed <= 80 + allowance:
    print(1)
else:
    print(2)
