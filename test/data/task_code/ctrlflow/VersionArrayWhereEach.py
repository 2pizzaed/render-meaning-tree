nums = [0,5,0,3]

max_odd = 0
for i in range(len(nums) - 1, -1, -1):
    if nums[i] % 2 != 0:
        max_odd = max(max_odd, nums[i])
    elif nums[i] == 0:
        nums[i] = max_odd
result = nums