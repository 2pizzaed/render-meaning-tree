elements = [5, 12, 8, 15, 20, 7, 18, 10]
processed = 0
for e in elements:
    if e > 10 and e < 18:
        continue
    processed = processed + e
print(processed)