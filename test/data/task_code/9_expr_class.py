from dataclasses import dataclass


@dataclass
class Expr:
    value: int | None = None
    op: str | None = None  # '+' / '*'
    left: 'Expr | None' = None
    right: 'Expr | None' = None


def eval(expr: Expr) -> int:
    if expr.value is not None:
        return expr.value
    elif expr.op == "+" and expr.left and expr.right:
        return eval(expr.left) + eval(expr.right)
    elif expr.op == "*" and expr.left and expr.right:
        return eval(expr.left) * eval(expr.right)
    return 0


# 2 + 9 * (3 + 5)
ex = Expr(
    op="+",
    left=Expr(2),
    right=Expr(
        op="*",
        left=Expr(9),
        right=Expr(
            op="+",
            left=Expr(3),
            right=Expr(5),
        ),
    ),
)

print(eval(ex))
