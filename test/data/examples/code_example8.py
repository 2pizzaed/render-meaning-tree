def g():
    if g():
        g()
    return (1, 2)

for step in g():
    print(step)
    g()

print('the end.')
