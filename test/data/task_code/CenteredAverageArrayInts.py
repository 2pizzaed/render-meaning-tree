nums = [1, 2, 3, 4, 100]

total = 0
mn = nums[0]
mx = nums[0]

for x in nums:
    total += x
    if x < mn:
        mn = x
    if x > mx:
        mx = x

result = (total - mn - mx) // (len(nums) - 2)
