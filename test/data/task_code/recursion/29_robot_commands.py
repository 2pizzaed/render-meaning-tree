# Робот на прямой: match выбирает шаг, рекурсия выполняет остальные команды
def run(cmds, pos):
    match cmds[0]:
        case "L":  # <! FT >
            pos -= 1
        case "R":  # <! T >
            pos += 1
    if len(cmds) == 1:  # <! FT >
        return pos
    return run(cmds[1:], pos)  # <! (-, "run(['L'], 1)") >

print(run(["R", "L"], 0))  # <! (-, "run(['R', 'L'], 0)") >
