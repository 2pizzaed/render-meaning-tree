nums = [4, 2, 2, 3]

for i in range(len(nums)):
    if nums[i] == 2:
        if not (
            (i > 0 and nums[i - 1] == 2) or (i < len(nums) - 1 and nums[i + 1] == 2)
        ):
            result = False
result = True