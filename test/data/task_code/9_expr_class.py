from dataclasses import dataclass


@dataclass
class Expr:
    value: int | None = None
    op: str | None = None  # '+' / '*'
    left: 'Expr | None' = None
    right: 'Expr | None' = None

    def eval(self) -> int:
        if self.value is not None:
            return self.value
        if self.op == "+" and self.left and self.right:
            return self.left.eval() + self.right.eval()
        if self.op == "*" and self.left and self.right:
            return self.left.eval() * self.right.eval()
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

print(ex.eval())
