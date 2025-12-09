N = 4
board = [[0] * N for _ in range(N)]

# направления: 0=вправо,1=вниз,2=влево,3=вверх
dirs = [(0, 1), (1, 0), (0, -1), (-1, 0)]


def print_board():
    for row in board:
        print(" ".join([f"{x:2d}" if x else " ." for x in row]))
    print()


def in_bounds(r, c):
    return 0 <= r < N and 0 <= c < N


def fill_spiral(r, c, direction, num, limit):
    board[r][c] = num
    # показать шаг (удобно для трассировки)
    print(f"Step {num}: placed at ({r},{c}), dir={direction}")
    print_board()

    if num == limit:
        return

    # попытка идти в том же направлении
    dr, dc = dirs[direction]
    nr, nc = r + dr, c + dc
    # если можно — идём
    if in_bounds(nr, nc) and board[nr][nc] == 0:
        fill_spiral(nr, nc, direction, num + 1, limit)
        return

    # иначе пробуем повернуть (право) — это вторая ветка
    nd = (direction + 1) % 4
    dr, dc = dirs[nd]
    nr, nc = r + dr, c + dc
    if in_bounds(nr, nc) and board[nr][nc] == 0:
        fill_spiral(nr, nc, nd, num + 1, limit)
        return

    # если и поворот не помог — пробуем ещё поворот (ещё правее) — третья ветка
    nd = (nd + 1) % 4
    dr, dc = dirs[nd]
    nr, nc = r + dr, c + dc
    if in_bounds(nr, nc) and board[nr][nc] == 0:
        fill_spiral(nr, nc, nd, num + 1, limit)
        return

    # наконец, четвёртая ветка — последний возможный поворот
    nd = (nd + 1) % 4
    dr, dc = dirs[nd]
    nr, nc = r + dr, c + dc
    if in_bounds(nr, nc) and board[nr][nc] == 0:
        fill_spiral(nr, nc, nd, num + 1, limit)
        return

    # если ни одно направление не доступно — завершаем (защита на всякий случай)
    return

# запускаем от (0,0) вправо
print("Start board:")
print_board()
fill_spiral(0, 0, 0, 1, N * N)

print("Final:")
print_board()
