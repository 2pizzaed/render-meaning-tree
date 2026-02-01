nums = [5, 4, 9, 4, 9, 5]

j = 0
check_count = 4
for i in range(len(nums) - 1):
    check = nums[i] == check_count
    if check:
        while nums[j] != 5 or (j > 0 and nums[j - 1] == 4):
            j += 1
        nums[j], nums[i + 1] = nums[i + 1], nums[j]
result = nums