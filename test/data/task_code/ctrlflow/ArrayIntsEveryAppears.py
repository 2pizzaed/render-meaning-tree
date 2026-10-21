nums = [4, 2, 2, 3]
s = nums[0]

result = True
for i in range(len(nums)):
    if nums[i] == 2:
        complex_condition = not (
            (i > 0 and nums[i - 1] == 2) or (i < len(nums) - 1 and nums[i + 1] == 2)
        )
        if complex_condition:
            result = False
            s = nums[i]
print(result)