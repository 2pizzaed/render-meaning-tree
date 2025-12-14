N = 4
board = [-1] * N  # board[row] = column ферзя в этой строке


def is_safe(row, col):
    for r in range(row):
        c = board[r]
        # Та же колонка?
        if c == col:
            return False
        # Диагонали?
        if abs(c - col) == abs(r - row):
            return False
    return True


solutions = []


def place_queen(row):
    if row == N:
        # нашли решение
        solutions.append(board.copy())
        return

    for col in range(N):
        if is_safe(row, col):
            board[row] = col
            place_queen(row + 1)
            board[row] = -1  # откат (важно для трассировки)


place_queen(0)

print("Найдено решений:", len(solutions))
for s in solutions:
    print(s)
