"""输入相对基准变了多少。只分档，不改求解，也不换成另一套班次。

分档还没有业务签认：相对基准不到 5% 不写；超过 5% 到 10% 记观察；超过 10% 记降级提示。
"""
import math


def rel(value, base=1.0):
    base = float(base)
    if base == 0:
        return None
    return abs(float(value) - base) / abs(base)


def level(value, base=1.0):
    r = rel(value, base)
    if r is None or r <= 0.05 + 1e-12:
        return ""
    if r <= 0.10 + 1e-12:
        return "观察"
    return "降级"


def psi(base, current):
    """占比漂移。当前占比减基准占比，再乘 ln(当前÷基准)，逐档相加。占比必须大于 0。"""
    total = 0.0
    for p, q in zip(base, current):
        p, q = float(p), float(q)
        if p <= 0 or q <= 0:
            raise ValueError("占比必须大于 0")
        total += (q - p) * math.log(q / p)
    return total
