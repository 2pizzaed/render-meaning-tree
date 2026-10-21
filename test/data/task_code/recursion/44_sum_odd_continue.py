# Сумма нечётных чисел: continue пропускает чётные
def sum_odd(nums):
    total = 0
    for x in nums:  # <! TTF >
        if x % 2 == 0:  # <! TF >
            continue
        total += x
    return total

print(sum_odd([2, 3]))  # <! (-, "sum_odd([2, 3])") >
