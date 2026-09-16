nums = [6, 2, 5, 3]

if len(nums) <= 1:
    result = list(nums)

result = nums[1:] + nums[:1]
print(result)
