# Тип дня недели: один case проверяет сразу несколько значений
def day_type(day):
    match day:
        case "сб" | "вс":  # <! FT >
            return "выходной"
        case "пт":  # <! T >
            return "короткий день"
        case _:
            return "рабочий"

print(day_type("пт"))  # <! (-, "day_type('пт')") >
print(day_type("вс"))  # <! (-, "day_type('вс')") >
