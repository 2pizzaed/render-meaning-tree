# Список гостей по умолчанию создаётся один раз и общий для всех вызовов
def add_guest(name, guests=[]):
    if name in guests:  # <! FT >
        print(name, "уже записан")
    else:
        guests.append(name)

add_guest("Аня")  # <! (-, "add_guest('Аня', [])") >
add_guest("Аня")  # <! (-, "add_guest('Аня', ['Аня'])") >
