# Проверка на простоту: else цикла выполняется, если делитель не найден
def check_prime(n):
    for d in range(2, n):  # <! TTTF >
        if n % d == 0:  # <! FFF >
            print(n, "делится на", d)
            break
    else:
        print(n, "простое")

number = 5
check_prime(number)  # <! (-, "check_prime(5)") >
