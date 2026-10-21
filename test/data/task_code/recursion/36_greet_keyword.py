# Параметр по умолчанию и именованный аргумент задают число повторов
def greet(name, times=1):
    while times > 0:  # <! TFTTF >
        print("Привет,", name)
        times -= 1

greet("Оля")  # <! (-, "greet('Оля', 1)") >
greet("Ян", times=2)  # <! (-, "greet('Ян', 2)") >
