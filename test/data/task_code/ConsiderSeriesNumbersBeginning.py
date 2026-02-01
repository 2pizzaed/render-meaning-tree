start = 0
end = 4

fin = []
for i in range(start, end):
    fizz = i % 3 == 0
    buzz = i % 5 == 0
    if fizz and buzz:
        fin.append("FizzBuzz")
    elif fizz:
        fin.append("Fizz")
    elif buzz:
        fin.append("Buzz")
    else:
        fin.append(str(i))
result = fin