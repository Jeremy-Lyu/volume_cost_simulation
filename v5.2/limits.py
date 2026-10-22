"""v5 极限搜索：网格并行扫描 + 二分细化，自动找临界点（示例数据）
可接受标准（⚠ 暂定，global_params 可改）：流失 = 0 且 最大月末积压 ≤ limit_max_backlog（默认 1000 台；基准本身 600 台）
预算标准：运营成本 ≤ 基准 × (1 + limit_budget_margin)（默认 3%）"""
import copy, os, time
import data_loader as dl, engine as en
from scenarios import apply_knobs
def ok_delivery(r, d): return r["lost"] < 0.5 and r["kpi"]["最大月末积压"] <= d["g"].get("limit_max_backlog", 1000)
def find_limits(specs, grid=6, refine=3, procs=6):
    """specs: [(维度, make(v)→d, ok(r,d)→bool, lo, hi)]，v 越大越难。所有维度的网格一起并行，再一起二分细化"""
    cases, idx = [], []
    for j, (nm, make, ok, lo, hi) in enumerate(specs):
        for g in range(grid):
            v = lo + (hi - lo) * g / (grid - 1); cases.append((make(v), f"{nm}={v:.3f}", {})); idx.append((j, v))
    res = en.run_many(cases, procs); st = {}
    for (j, v), r in zip(idx, res): st.setdefault(j, []).append((v, specs[j][2](r, specs[j][1](v))))
    br = {}
    for j, pts in st.items():
        pts.sort(); oks = [o for _, o in pts]
        if all(oks): br[j] = (pts[-1][0], None, "≥扫描上限")
        elif not oks[0]: br[j] = (pts[0][0], None, "≤扫描下限")
        else: k = oks.index(False); br[j] = (pts[k-1][0], pts[k][0], "")
    for _ in range(refine):
        todo = [j for j, (a, b, _) in br.items() if b is not None]
        if not todo: break
        mids = {j: (br[j][0] + br[j][1]) / 2 for j in todo}
        rr = en.run_many([(specs[j][1](mids[j]), f"{specs[j][0]}={mids[j]:.3f}", {}) for j in todo], procs)
        for j, r in zip(todo, rr):
            a, b, n = br[j]; m = mids[j]
            br[j] = (m, b, n) if specs[j][2](r, specs[j][1](m)) else (a, m, n)
    return {specs[j][0]: (a, b, n) for j, (a, b, n) in br.items()}
def run(base, procs=6, out=None):
    out = out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "v5")
    os.makedirs(out, exist_ok=True); t0 = time.time()
    b0 = en.solve_case(base, "基准"); m = base["g"].get("limit_budget_margin", 0.03)
    budget = b0["kpi"]["运营成本"] * (1 + m); lim = base["g"].get("limit_max_backlog", 1000)
    def fast(d): d["g"]["solver_time_limit"] = 30; d["g"]["mip_rel_gap"] = 2e-3; return d
    okb = lambda r, d: r["kpi"]["运营成本"] <= budget
    specs = [("全年需求上浮", lambda f: fast(apply_knobs(base, {"demand_all": 1 + f})), ok_delivery, 0.0, 0.6)]
    specs += [(f"{s} 10月停线天数", (lambda n, s=s: fast(apply_knobs(base, {"down": {f"{s}|10": n}}))), ok_delivery, 0.0, float(base["days"][10])) for s in base["shops"]]
    specs += [(f"{s} 全年有效产能下降", (lambda f, s=s: fast(apply_knobs(base, {"avail": {f"{s}|{t}": 1 - f for t in base["months"]}}))), ok_delivery, 0.0, 0.85) for s in base["shops"]]
    specs += [("工资上涨", lambda f: fast(apply_knobs(base, {"wage": 1 + f})), okb, 0.0, 0.3), ("电价上涨", lambda f: fast(apply_knobs(base, {"elec": 1 + f})), okb, 0.0, 1.0)]
    br = find_limits(specs, procs=procs); rows = []
    for nm, (a, b, note) in br.items():
        if "天" in nm: val, mean = f"{a:.1f} 天", "旺季该车间最多可停线天数（其余条件不变）"
        elif "需求" in nm: val, mean = f"+{a:.1%}", f"超过后出现流失或月末积压>{lim:.0f}台"
        elif "产能下降" in nm: val, mean = f"−{a:.1%}", "崩溃阈值：有效产能再降则交付不达标"
        else: val, mean = f"+{a:.1%}", f"超过后运营成本 > 预算(基准+{m:.0%}={budget/1e4:,.0f}万)"
        rows.append(dict(维度=nm, 临界值=val, 区间=f"[{a:.3f}, {b:.3f}]" if b is not None else "-", 含义=mean, 备注=note))
    import report as rp; rp.write_csv(os.path.join(out, "安全边界表.csv"), rows); plot(rows, os.path.join(out, "安全边界图.png"))
    return rows, time.time() - t0
def plot(rows, path):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    import cjkfont; cjkfont.use()
    pct = [r for r in rows if "%" in r["临界值"]]; day = [r for r in rows if "天" in r["临界值"]]
    fig, ax = plt.subplots(1, 2, figsize=(16, 7))
    vals = [abs(float(r["临界值"].strip("+−%"))) for r in pct]
    ax[0].barh([r["维度"] for r in pct], vals, color=["#c62828" if v < 5 else "#f9a825" if v < 15 else "#2e7d32" for v in vals])
    for i, v in enumerate(vals): ax[0].text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=11)
    ax[0].set_title("安全余量（%）：越短越脆弱", fontsize=14); ax[0].invert_yaxis()
    dv = [float(r["临界值"].split()[0]) for r in day]
    ax[1].barh([r["维度"] for r in day], dv, color="#1565c0")
    for i, v in enumerate(dv): ax[1].text(v + 0.1, i, f"{v:.1f} 天", va="center", fontsize=11)
    ax[1].set_title("旺季（10月）最多可停线天数", fontsize=14); ax[1].invert_yaxis()
    fig.suptitle("v5 安全边界（示例数据；交付标准：无流失且月末积压≤1000台 ⚠；预算=基准+3% ⚠）", fontsize=15)
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)
if __name__ == "__main__":
    rows, sec = run(dl.load()); [print(r) for r in rows]; print(f"用时 {sec:.0f}s")
