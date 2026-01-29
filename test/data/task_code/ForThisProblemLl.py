num = 16

digit = num % 10
if digit >= 5:
    result = num + (10 - digit)
result = num - digit