"""v5 提速：统一求解入口 + 参数哈希缓存 + 多进程并行
solve_case(d, name, **kw) → 结果字典（状态、目标、KPI、成本科目、plan、选中模式 y）
run_many([(d, name, kw), ...], procs) 并行；同参数第二次直接读缓存 .cache/<hash>.pkl"""
import hashlib, os, pickle, time
import multiprocessing as _mp
import model_builder as mb, report as rp
H = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.join(H, ".cache")
def _canon(o):
    if isinstance(o, dict): return "{" + ",".join(f"{_canon(k)}:{_canon(v)}" for k, v in sorted(o.items(), key=lambda kv: repr(kv[0]))) + "}"
    if isinstance(o, (list, tuple)): return "[" + ",".join(_canon(x) for x in o) + "]"
    if isinstance(o, float): return repr(round(o, 9))
    return repr(o)
def phash(d, kw):
    src = b"".join(open(os.path.join(H, n), "rb").read() for n in ("model_builder.py", "cost_functions.py", "energy.py", "report.py"))   # v5.1：能源层/报表变更也使缓存失效
    dd = dict(d); dd["g"] = {k: v for k, v in d["g"].items() if k != "threads"}
    return hashlib.sha1((_canon(dd) + _canon(kw)).encode() + src).hexdigest()[:20]
def solve_case(d, name="", use_cache=True, **kw):
    key = phash(d, kw); p = os.path.join(CACHE, key + ".pkl")
    if use_cache and os.path.exists(p):
        r = pickle.load(open(p, "rb")); r.update(name=name, cached=True, solve_seconds=r.get("solve_seconds", r["seconds"]), seconds=0.0); return r
    t0 = time.time(); P, v = mb.build(d, **kw); st, obj = mb.solve(P, d)
    if any(var.value() is None for var in v["y"].values()):          # 资源争抢下超时无可行解 → 放宽时限重试一次
        d = dict(d); d["g"] = dict(d["g"], solver_time_limit=3 * d["g"]["solver_time_limit"]); P, v = mb.build(d, **kw); st, obj = mb.solve(P, d)
    plan, cost, out, sh = rp.extract(d, v); err = rp.selfcheck(d, v, obj)
    assert not err, f"{name} 守恒自检失败: {err}"
    k = rp.kpis(d, v, plan, cost, out, obj)
    r = dict(name=name, status=st, obj=obj, out=out, lost=sh, kpi=k, cost=cost, plan=plan,
             y={kk: round(var.value()) for kk, var in v["y"].items()}, seconds=time.time() - t0, cached=False, hash=key); r["solve_seconds"] = r["seconds"]
    os.makedirs(CACHE, exist_ok=True); pickle.dump(r, open(p, "wb")); return r
def _job(a): d, name, kw = a; return solve_case(d, name, **kw)
def run_many(cases, procs=4):
    """cases = [(d, name, kw)]；并行时每个求解器限 1 线程，避免抢核"""
    for d, _, _ in cases: d["g"]["threads"] = 1 if procs > 1 else d["g"].get("threads", 0)
    if procs <= 1 or len(cases) == 1: return [_job(c) for c in cases]
    with _mp.get_context("spawn").Pool(min(procs, len(cases))) as pool: return pool.map(_job, cases)   # spawn：父进程用过 HiGHS 后再 fork 会导致子进程求解失败
def chosen(y): return [k for k, v in y.items() if v == 1]
