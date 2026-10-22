"""P3b：跨厂协同调产（多厂联合优化第一版）
思路：先用各厂自身的月模型采样"产量→成本"曲线（凸性近似），再用分配 LP 在总需求约束下
      把产量分配到各厂，超出本厂基准需求的部分按跨厂转运成本计费（简化转移定价 ⚠）。
用法：python3 multiplant.py [厂1] [厂2] ...     默认 data/ plants/DEMO_B
可选：transfer.csv(from_plant,to_plant,cost_per_unit,max_units) 覆盖默认转运成本
输出：output/multiplant_curve.csv（各厂成本曲线）、output/multiplant_alloc.csv（分配方案与对比）
说明：曲线采样需要对每个厂求解多次（约 5 点/厂），耗时分钟级；属离线分析，非日常排产"""
import copy, csv, os
import pulp
import data_loader as dl, model_builder as mb, report as rp
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, "output")
SCALES = [0.6, 0.8, 1.0, 1.2, 1.4]
CURVE_TIME_LIMIT = 30          # 曲线采样每次求解时限（秒），避免离线分析跑太久
def cost_at(pkg, scale):
    """在给定需求缩放下求解该厂，返回 (总成本元, 产量, 缺口, 状态)"""
    d = copy.deepcopy(dl.load(os.path.join(H, pkg)))
    d["demand"] = {k: v * scale for k, v in d["demand"].items()}
    d["g"]["solver_time_limit"] = CURVE_TIME_LIMIT
    P, v = mb.build(d); st, obj = mb.solve(P, d)
    plan, cost, out, sh = rp.extract(d, v)
    return obj, out, sh, st
def build_curve(pkg):
    rows = []
    for s in SCALES:
        obj, out, sh, st = cost_at(pkg, s)
        rows.append(dict(配置包=pkg, 需求缩放=s, 状态=st, 总成本_万元=round(obj/1e4), 产量=round(out), 缺口=round(sh),
                         单车成本_元=round(obj/max(out, 1))))
        print(f"  {pkg:<22} 缩放{s:>4}: {st:<8} 产量 {out:>8,.0f} 缺口 {sh:>7,.0f} 成本 {obj/1e4:>9,.0f}万")
    return rows
def main(pkgs, demand_scale=1.0):
    curves = {p: build_curve(p) for p in pkgs}
    rp.write_csv(os.path.join(OUT, "multiplant_curve.csv"), [r for p in pkgs for r in curves[p]])
    base = {p: next(r["产量"] for r in curves[p] if r["需求缩放"] == 1.0) for p in pkgs}
    total = sum(base.values()) * demand_scale
    transfer_cost = {p: 800.0 for p in pkgs}      # 默认跨厂转运成本 元/台（⚠ 用 transfer.csv 覆盖）
    tp = os.path.join(H, "transfer.csv")
    if os.path.exists(tp):
        for r in csv.DictReader(open(tp, encoding="utf-8")):
            if r["from_plant"] in transfer_cost: transfer_cost[r["from_plant"]] = float(r["cost_per_unit"])
    P = pulp.LpProblem("MultiPlantAlloc", pulp.LpMinimize)
    lam = {p: [pulp.LpVariable(f"lam_{p}_{i}", lowBound=0) for i in range(len(curves[p]))] for p in pkgs}
    v = {p: pulp.LpVariable(f"v_{p}", lowBound=0) for p in pkgs}
    tr = {p: pulp.LpVariable(f"tr_{p}", lowBound=0) for p in pkgs}
    for p in pkgs:
        P += pulp.lpSum(lam[p]) == 1, f"sum_{p}"
        P += v[p] == pulp.lpSum(lam[p][i] * curves[p][i]["产量"] for i in range(len(curves[p]))), f"vol_{p}"
        P += tr[p] >= v[p] - base[p]
    P += pulp.lpSum(v.values()) == total, "total_demand"
    P += pulp.lpSum(lam[p][i] * curves[p][i]["总成本_万元"] for p in pkgs for i in range(len(curves[p]))) \
         + pulp.lpSum(transfer_cost[p] * tr[p] / 1e4 for p in pkgs)
    P.solve(pulp.PULP_CBC_CMD(msg=False))
    rows, alloc, cost_alloc = [], 0.0, 0.0
    for p in pkgs:
        a = v[p].value() or 0
        c = sum((lam[p][i].value() or 0) * curves[p][i]["总成本_万元"] for i in range(len(curves[p])))
        tc = (tr[p].value() or 0) * transfer_cost[p] / 1e4
        rows.append(dict(工厂=p, 本地基准产量=base[p], 协同分配产量=round(a), 增减=round(a-base[p]),
                         转运台数=round(tr[p].value() or 0), 转运成本_万元=round(tc, 1), 制造成本_万元=round(c, 1),
                         合计_万元=round(c+tc, 1)))
        alloc += c + tc
    # 对照：把总需求按同一比例分给各厂（各自本地扩产，无转运）
    share = {p: base[p] / sum(base.values()) for p in pkgs}
    local = 0.0
    for p in pkgs:
        q = total * share[p]
        pts = [(r["产量"], r["总成本_万元"]) for r in curves[p]]
        local += _interp(pts, q)
    rp.write_csv(os.path.join(OUT, "multiplant_alloc.csv"), rows)
    print(f"\n=== 跨厂协同分配（示例数据，总需求 {total:,.0f} 台 = 基准 ×{demand_scale}）===")
    for r in rows: print(" ", r)
    print(f"\n对照：各厂按原比例本地扩产 {local:,.0f} 万 → 协同分配合计 {alloc:,.0f} 万，节约 {local-alloc:,.0f} 万")
    print("⚠ 曲线为凸性近似、转运成本为简化转移定价；用于方向判断，不作为结算依据")
def _interp(pts, q):
    """在采样点上线性插值总成本（分段线性凸曲线）"""
    pts = sorted(pts)
    if q <= pts[0][0]: return pts[0][1]
    for (x0,y0),(x1,y1) in zip(pts, pts[1:]):
        if q <= x1: return y0 + (y1-y0)*(q-x0)/max(x1-x0, 1)
    return pts[-1][1]
if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    scale = float(a[-1]) if a and a[-1].replace(".","",1).isdigit() else 1.0
    pk = a[:-1] if scale != 1.0 or (a and a[-1].replace(".","",1).isdigit()) else a
    main(pk or ["data", "plants/DEMO_B"], scale)