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
    elif expr.op == "+":
        return eval(expr.left) + eval(expr.right)
    elif expr.op == "*":
        return eval(expr.left) * eval(expr.right)
    return 0


# 4 + 7 * (1 + 3)
ex = Expr(op="+", left=Expr(4) )
e2 = Expr(op="*", left=Expr(7) )
e3 = Expr(op="+", left=Expr(1), right=Expr(3) )
ex.right = e2
e2.right = e3
print(eval(ex))

