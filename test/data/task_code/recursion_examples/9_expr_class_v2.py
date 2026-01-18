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
        left_val = eval(expr.left)
        right_val = eval(expr.right)
        return left_val + right_val
    elif expr.op == "*":
        left_val = eval(expr.left)
        right_val = eval(expr.right)
        return left_val * right_val
    return 0


# 3 + 6 * (2 + 4)
ex = Expr(op="+", left=Expr(3) )
e2 = Expr(op="*", left=Expr(6) )
e3 = Expr(op="+", left=Expr(2), right=Expr(4) )
ex.right = e2
e2.right = e3
print(eval(ex))
