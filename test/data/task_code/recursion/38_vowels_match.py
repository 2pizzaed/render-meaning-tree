# Подсчёт гласных: рекурсия по строке, match по первой букве
def vowels(s):
    if s == "":  # <! FFT >
        return 0
    match s[0]:
        case "а" | "о" | "у":  # <! TF >
            return 1 + vowels(s[1:])  # <! (-, "vowels('н')") >
        case _:
            return vowels(s[1:])  # <! (-, "vowels('')") >

print(vowels("он"))  # <! (-, "vowels('он')") >
