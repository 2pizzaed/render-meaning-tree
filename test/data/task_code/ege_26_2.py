items = [
    (10, 60),
    (20, 100),
    (30, 120),
    (15, 80),
    (25, 110)
]
max_weight = 100

items.sort()

total_value = 0
total_weight = 0
count = 0
for weight, value in items:
    if total_weight + weight <= max_weight:
        total_weight = total_weight + weight
        total_value = total_value + value
        count = count + 1
print(count, total_value)
