"""v5 一键运行：提速基准测试 → 极限搜索 → 策略扫描/帕累托/推荐/前三 → 预测与风险 → 稳健方案 → 瀑布/影子价格 → 决策单 + 统一 Excel（示例数据）"""
import copy, json, os, time
import data_loader as dl, engine as en, report as rp
import limits, strategy_v5 as sv, forecast as fc, risk, outputs_v5 as ov
from scenarios import apply_knobs
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, "output", "v5")
def main(procs=6, n_eval=40):
    os.makedirs(OUT, exist_ok=True); base = dl.load(); T = {}
    # 0 提速：串行 vs 并行（不用缓存），再测缓存命中
    cases = [(dl.scenario(base, **kw), n, {}) for n, kw in [("基准", {}), ("需求+10%", {"demand": 1.1}), ("需求-10%", {"demand": 0.9}), ("电价+20%", {"elec": 1.2}), ("工资+5%", {"wage": 1.05})]]
    for d, _, _ in cases: d["g"]["solver_time_limit"] = 200
    t = time.time(); [en.solve_case(copy.deepcopy(d), n, use_cache=False) for d, n, _ in cases]; T["5场景串行(无缓存)"] = time.time() - t
    t = time.time(); r5 = en.run_many([(copy.deepcopy(d), n, dict(use_cache=False)) for d, n, k in cases], procs); T[f"5场景并行×{procs}(无缓存)"] = time.time() - t
    t = time.time(); en.run_many([(copy.deepcopy(d), n, k) for d, n, k in cases], procs); T["5场景缓存命中"] = time.time() - t
    r0 = en.solve_case(copy.deepcopy(base), "成本优先(基准)")
    budget = r0["kpi"]["运营成本"] * (1 + base["g"].get("limit_budget_margin", 0.03))
    # 1 极限搜索
    t = time.time(); bounds, _ = limits.run(base, procs=procs, out=OUT); T["极限搜索"] = time.time() - t
    # 2 策略
    t = time.time(); rows, res = sv.sweep(base, procs); rec, why = sv.recommend(rows)
    wcsv(os.path.join(OUT, "帕累托与策略扫描.csv"), rows); T["策略扫描(17组权重)"] = time.time() - t; T["策略扫描:单次求解秒(首次,合计)"] = sum(r.get("solve_seconds", r["seconds"]) for r in res)
    w = next(g for g, r in zip(sv.GRID, rows) if r["方案"] == rec["方案"])
    t = time.time(); alts = sv.top3(base, w); T["前三备选"] = time.time() - t
    alt_rows = [dict(sv.metrics(a), 与备选1差异=sv.mode_diff(alts[0]["plan"], a["plan"]) if j else "-") for j, a in enumerate(alts)]
    wcsv(os.path.join(OUT, "前三备选.csv"), alt_rows); plot_pareto(rows, rec)
    # 3 预测 + 风险
    t = time.time(); qt = fc.quantile_table(base); wcsv(os.path.join(OUT, "预测分位数.csv"), qt)
    ev = fc.sample_scenarios(base, n_eval, seed=7)
    rec_r = next(r for r in res if r["name"] == rec["方案"])
    risk_rows, dists = [], {}
    for nm, y in (("成本优先(确定性)", r0["y"]), (f"推荐:{rec['方案']}", rec_r["y"])):
        row, c = risk.evaluate(base, y, ev, nm, procs, budget); risk_rows.append(row); dists[nm] = c
    T["预测+风险评估"] = time.time() - t
    # 4 稳健
    import pickle; rp_ = os.path.join(en.CACHE, f"robust_plans_{en.phash(base, {'robust': 1})}.pkl")   # v5.1 修复：缓存键含参数与代码哈希，改模型后不再读旧稳健方案; t = time.time()
    if os.path.exists(rp_): rob, T["稳健优化(3种模式,各8情景)"] = pickle.load(open(rp_, "rb"))
    else: rob = risk.robust_plans(base); T["稳健优化(3种模式,各8情景)"] = time.time() - t; pickle.dump((rob, T["稳健优化(3种模式,各8情景)"]), open(rp_, "wb"))
    t = time.time()
    for m, (st, obj, y) in rob.items():
        row, c = risk.evaluate(base, y, ev, f"稳健:{dict(mean='期望',cvar='CVaR90',chance='90%情景不流失')[m]}", procs, budget)
        row["训练状态"] = st; risk_rows.append(row); dists[row["方案"]] = c
    T["稳健方案样本外评估"] = time.time() - t
    wcsv(os.path.join(OUT, "风险与稳健对比.csv"), risk_rows); plot_dist(dists, budget)
    # 5 瀑布 + 影子价格
    # v5.1 修复：决策单/瀑布/结论统一用"扫描口径"的成本优先（与推荐、备选同 gap 与时限），不再混用精解 r0
    r0s = next(r for r in res if r["name"] == "成本优先")
    wf = ov.waterfall(r0s, rec_r, os.path.join(OUT, "成本瀑布_成本优先_vs_推荐.png"), "成本优先", f"推荐:{rec['方案']}")
    t = time.time(); sp = ov.shadow_prices(base, r0, procs); wcsv(os.path.join(OUT, "影子价格.csv"), sp); T["影子价格"] = time.time() - t
    # 6 决策单 + Excel
    ctx = dict(标题="11 月起年度产能与人力方案 · 管理层决策单（示例）", 版本=f"配置 {base['plant']['config_version']} ｜ core v5 ｜ gap≤0.2%（扫描）",
               结论=why, 瀑布基准_万元=round(r0s["kpi"]["运营成本"]/1e4), 结论基准_万元=next(r["运营成本_万元"] for r in rows if r["方案"] == "成本优先"), 基准口径="成本优先（扫描口径：gap≤0.2%、时限 40s，与推荐/备选一致）", 方案=[sv.metrics(r0s) | {"方案": "成本优先"}] + alt_rows, 瀑布=wf, 风险=risk_rows, 边界=bounds, 影子=sp,
               拍板=["是否采用推荐策略（相对成本优先多付的成本是否接受）", "冲压人均加班到 60h/月 是否允许 ⚠HR", "延期交付是否可对客户承诺（延期成本 1500 元/台·月 ⚠）"],
               假设=["全部为示例数据", "加班绝对上限 60h/人·月 ⚠ 待 HR 确认", "交付标准：无流失且月末积压≤1000台 ⚠", "预算=基准+3% ⚠", "权重换算 3000元/人变化、5000元/台·月积压、1000元/人·月 ⚠", "预测历史为生成的示例历史 ⚠"])
    ov.decision_sheet(ctx, os.path.join(OUT, "管理层决策单.md"), os.path.join(OUT, "管理层决策单.png"))
    timing = [dict(步骤=k, 秒=round(v, 1)) for k, v in T.items()]; wcsv(os.path.join(OUT, "运行耗时.csv"), timing)
    sm = [dict(场景=r["name"], 状态=r["status"], 运营成本_万元=round(r["kpi"]["运营成本"]/1e4), 单车_元=round(r["kpi"]["单车成本"]), 延期台月=round(r["kpi"]["延期台月"]),
               流失台=round(r["lost"]), 超限加班h=round(r["kpi"]["超限加班h"]), 求解秒=round(r["seconds"], 1)) for r in r5]
    ov.excel(os.path.join(OUT, "模拟器v5_输出.xlsx"), {
        "决策单": open(os.path.join(OUT, "管理层决策单.md"), encoding="utf-8").read().split("\n"),
        "场景总览": sm, "方案明细_成本优先": r0s["plan"], "方案明细_推荐": rec_r["plan"],
        "成本科目": [dict(科目=k, 成本优先_元=round(r0s["cost"].get(k, 0)), 推荐_元=round(rec_r["cost"].get(k, 0))) for k in dict.fromkeys(list(r0s["cost"]) + list(rec_r["cost"]))],
        "成本瀑布": wf, "策略扫描_帕累托": rows, "前三备选": alt_rows, "安全边界": bounds, "风险与稳健": risk_rows, "预测分位数": qt,
        "影子价格": sp, "运行耗时": timing, "假设参数": [dict(参数=k, 值=v) for k, v in base["g"].items()]})
    json.dump(dict(推荐=rec, 理由=why, 耗时=T), open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(why); [print(r) for r in risk_rows]; print(T)
def wcsv(path, rows):
    import csv
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, keys, restval=""); w.writeheader(); w.writerows(rows)
def plot_pareto(rows, rec):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(16, 6.5))
    for a, yk, yl in ((ax[0], "人数变化合计", "全年人数变化合计（人）"), (ax[1], "延期台月", "延期（台·月）")):
        for r in rows:
            c = "#c62828" if r["方案"] == rec["方案"] else ("#1565c0" if r["帕累托"] else "#b0bec5")
            a.scatter(r["运营成本_万元"], r[yk], s=90 if r["帕累托"] else 40, c=c, zorder=3)
        for r in rows:
            if r["帕累托"] or r["方案"] == "成本优先": a.annotate(r["方案"], (r["运营成本_万元"], r[yk]), fontsize=8.5, xytext=(4, 4), textcoords="offset points")
        a.set_xlabel("运营成本（万元）"); a.set_ylabel(yl); a.grid(alpha=.3)
    fig.suptitle("帕累托前沿（蓝=前沿，红=推荐，灰=被支配；示例数据）", fontsize=14); fig.tight_layout()
    fig.savefig(os.path.join(OUT, "帕累托前沿.png"), dpi=120); plt.close(fig)
def plot_dist(dists, budget):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(14, 6.5))
    ax.boxplot(list(dists.values()), tick_labels=list(dists.keys()), vert=False, showmeans=True)
    ax.axvline(budget / 1e4, color="#c62828", ls="--"); ax.text(budget / 1e4, 0.55, f" 预算 {budget/1e4:,.0f} 万 ⚠", color="#c62828")
    ax.set_xlabel("运营成本（万元）"); ax.set_title("各方案在预测分布 40 个样本下的成本分布（示例数据）", fontsize=14); fig.tight_layout()
    fig.savefig(os.path.join(OUT, "成本分布_风险.png"), dpi=120); plt.close(fig)
if __name__ == "__main__": main()
