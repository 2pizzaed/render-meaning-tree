# ----- Глобальная область -----

def transform_value(x):
    # Функция 1: несколько условий и цикл
    total = 0
    for i in range(1, x + 1):
        if i % 2 == 0:
            total += i
        else:
            if i % 3 == 0:
                total -= i
            else:
                total += 1
    return total


def compute_sequence(n):
    # Функция 2: цикл while + вложенные условия + early-break/continue
    seq = []
    i = 0

    while i < n:
        if i % 5 == 0:
            i += 1
            continue

        if i % 2 == 0:
            seq.append(i * 2)
        else:
            if i % 3 == 0:
                seq.append(i // 3)
            else:
                seq.append(i + 7)

        if len(seq) > 10:
            break

        i += 1

    return seq

# ----- Глобальный код -----

value = 8
result1 = transform_value(value)

limit = 15
result2 = compute_sequence(limit)