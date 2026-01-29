source = 320
dst = 2
s = ''
sourcei = source
while source != 0:
    s += str(source % dst)
    source //= dst
s = reverse(s)
print(s)