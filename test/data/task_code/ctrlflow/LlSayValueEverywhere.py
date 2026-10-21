nums = [1, 2, 1, 3]
val = 1

for i in range(len(nums) - 1):
    if nums[i] != val and nums[i + 1] != val:
        result = False
result = True