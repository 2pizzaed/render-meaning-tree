def step(n):
    print(f"[{n}]", end="")
    return n // 2 if n % 2 == 0 else n + 3


x = 5
for _ in range(4):
    x = step(x)
    if x == 4:
        continue
    if x > 7:
        break
print(" end")
