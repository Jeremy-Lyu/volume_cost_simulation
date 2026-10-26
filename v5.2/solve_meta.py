"""一次求解的精度记录。不改目标，也不改约束。

HiGHS 固定 random_seed，线程空着或写成 0 时用 1 线程。
多线程下同一输入可以落到间隙里的另一个解。金标和决策卡都走这一条。
"""
import pulp


def make_solver(time_limit, gap, threads=None, seed=1):
    """返回 (solver, 实际线程, 种子)。有 HiGHS 就用 HiGHS。"""
    threads = int(threads or 0)
    if threads <= 0:
        threads = 1
    seed = int(1 if seed is None else seed)
    if "HiGHS" in pulp.listSolvers(True):
        solver = pulp.HiGHS(msg=False, timeLimit=time_limit, gapRel=gap, threads=threads, random_seed=seed)
        return solver, threads, seed
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=int(time_limit), gapRel=gap, threads=threads)
    return solver, threads, seed


def meta_from(P, obj, gap_setting, time_limit, seconds, threads, seed):
    """下界和 Gap 来自求解器。触时限时，状态仍可能打印 Optimal。"""
    bound = gap = None
    model_status = ""
    sm = getattr(P, "solverModel", None)
    if sm is not None and hasattr(sm, "getInfoValue"):
        try:
            bound = float(sm.getInfoValue("mip_dual_bound")[1])
        except Exception:
            bound = None
        try:
            gap = float(sm.getInfoValue("mip_gap")[1])
        except Exception:
            gap = None
        try:
            model_status = str(sm.getModelStatus())
        except Exception:
            model_status = ""
    if gap is None and bound is not None and obj:
        gap = abs(float(obj) - float(bound)) / abs(float(obj))
    hit = ("TimeLimit" in model_status) or (time_limit is not None and seconds >= float(time_limit) - 0.05)
    return dict(
        求解器状态=model_status,
        下界=bound,
        Gap=gap,
        设定Gap=gap_setting,
        求解秒=round(float(seconds), 1),
        时限秒=time_limit,
        触时限=bool(hit),
        线程=threads,
        种子=seed,
    )
