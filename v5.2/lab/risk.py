"""v5 预测驱动风险评估 + 稳健方案对比（示例数据）
1) forecast 得 P10/P50/P90；2) 抽 N_eval 个样本（需求×开动率）；3) 固定方案模式(fix_y)，每个样本重算加班/产量/积压；
4) 输出 P(流失)、P(积压超限)、P(成本>预算)、成本分布（均值/P10/P50/P90/CVaR90）"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import copy, os, statistics as stt
import multiprocessing as _mp
import engine as en, forecast as fc, robust as rb
def scen_d(base, sc):
    d = copy.deepcopy(base); d["demand"] = dict(sc["demand"]); d["avail"] = dict(sc["avail"])
    d["g"]["solver_time_limit"] = 30; return d
def evaluate(base, y, scens, name, procs=6, budget=None, lim=None):
    res = en.run_many([(scen_d(base, sc), f"{name}#{i}", dict(fix_y=y)) for i, sc in enumerate(scens)], procs)
    c = sorted(r["kpi"]["运营成本"] / 1e4 for r in res); n = len(c)
    q = lambda p: c[min(n - 1, int(p * (n - 1) + 0.5))]
    tail = c[int(0.9 * n):] or c[-1:]
    lim = lim or base["g"].get("limit_max_backlog", 1000)
    return dict(方案=name, 样本数=n, 平均成本_万元=round(stt.mean(c)), P10=round(q(.1)), P50=round(q(.5)), P90=round(q(.9)), CVaR90=round(stt.mean(tail)),
                P_流失=f"{sum(r['lost'] > 0.5 for r in res)/n:.0%}", P_积压超限=f"{sum(r['kpi']['最大月末积压'] > lim for r in res)/n:.0%}",
                P_成本超预算=f"{sum(r['kpi']['运营成本'] > budget for r in res)/n:.0%}" if budget else "-",
                平均延期台月=round(stt.mean(r["kpi"]["延期台月"] for r in res)), 平均流失=round(stt.mean(r["lost"] for r in res))), c
def _rob(a):
    base, scens, mode = a; return mode, rb.solve_robust(base, scens, mode=mode, alpha=0.9, lam=0.5, time_limit=240)
def robust_plans(base, n_train=8, seed=101, modes=("mean", "cvar", "chance")):
    scens = fc.sample_scenarios(base, n_train, seed=seed)
    with _mp.get_context("spawn").Pool(len(modes)) as p: out = p.map(_rob, [(base, scens, m) for m in modes])
    return {m: r for m, r in out}
