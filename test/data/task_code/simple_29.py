n = 10
sum_even = 0
sum_odd = 0

while n > 0:
    if n % 2 == 0:
        sum_even = sum_even + n
    else:
        sum_odd = sum_odd + n
    n = n - 1

print(sum_even)
print(sum_odd)
