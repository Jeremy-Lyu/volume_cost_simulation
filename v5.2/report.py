"""块12：报表——方案明细、成本分项、单车成本、财务口径对照"""
import csv, os, pulp, cost_functions as cf
NON_OBJ = ("物料",)   # 只做口径、不进目标的科目

def extract(d, v):
    """v4：成本分项直接取目标函数里的科目表达式 v["acc"]，保证 Σ分项 ≡ 目标值。"""
    plan = []
    S, M, T = d["shops"], d["models"], d["months"]
    cost = {k: (pulp.value(e) or 0.0) for k, e in v["acc"].items()}
    for (s,i,k,t), var in v["y"].items():
        if var.value() > 0.5:
            o = d["jph"][s][i]; otv = v["ot"][(s,i,t)].value() or 0; otx = v["otx"][(s,i,t)].value() or 0
            vol = sum(v["x"][(s,m,t)].value() for m in M)
            heads, ind = (o["heads"] * k, cf.indirect_heads(d, s, o) * k)
            sd = (v.get("sdo") or {}).get((s,i,k,t)); sd = sd.value() if sd is not None else 0.0
            jl = (v.get("jlost") or {}).get((s,t)); jl = jl.value() if jl is not None else 0.0
            cap = cf.capacity(d,s,o,k,t) + cf.ot_units(d,s,o,t,otv+otx) - cf.cap_per_day(d,s,o,k,t) * (sd or 0) - (jl or 0)
            plan.append(dict(shop=s, month=t, jph=o["jph"], shifts=k, heads=heads, indirect_heads=ind, total_heads=heads+ind,
                             ot_hours=round(otv+otx,1), ot_excess_hours=round(otx,1),
                             ot_per_head=round((otv+otx)/k,1) if k else 0.0,
                             capacity=round(cap), volume=round(vol),
                             util=round(vol/(cap + cf.cap_per_day(d,s,o,k,t)*(sd or 0) + (jl or 0)),3) if cap else 0, capacity_gross=round(cap + cf.cap_per_day(d,s,o,k,t)*(sd or 0) + (jl or 0)), buffer_cap=cf.buffer_cap(d,s),
                             buffer_end=round(sum(v["inv"][(s,m,t)].value() for m in M)) if s != S[-1] else 0,
                             stop_days=round(sd or 0, 2), jph_switch_lost=round(jl or 0), borrowed=round(((v.get("bw") or {}).get((s,t)).value() or 0) if (v.get("bw") or {}).get((s,t)) is not None else 0, 1),
                             ftt=round(cf.ftt(d,s),4), oee=round(cf.oee(d,s,t),4), attendance=round(cf.attendance(d,s,t),4)))
    mat = sum(cf.mat_cost(d, m, t) * v["x"][(S[-1],m,t)].value() for m in M for t in T)
    if mat: cost["物料"] = mat
    sh = sum(var.value() for var in v["short"].values())
    out = sum(v["x"][(S[-1],m,t)].value() for m in M for t in T)
    plan.sort(key=lambda r: (S.index(r["shop"]), r["month"]))
    return plan, cost, out, sh

def kpis(d, v, plan, cost, out, obj):
    """v4 统一口径：运营成本 = 目标 − 惩罚 + 边际贡献（不含物料）；单车 = 运营成本/产量"""
    T = d["months"]
    pen = cost.get("缺口惩罚(流失)", 0); mg = -cost.get("−边际贡献", 0)
    wt = sum(v for k, v in cost.items() if k.startswith("权重:"))     # v5 权重项不计入运营成本
    op = obj - pen + mg - wt
    sw, tot = [], 0.0
    for s in d["shops"]:
        h = [r["total_heads"] for r in plan if r["shop"] == s]
        sw += [abs(h[i]-h[i-1])/max(h[i-1], 1) for i in range(1, len(h))]; tot += sum(abs(h[i]-h[i-1]) for i in range(1, len(h)))
    return dict(运营成本=op, 单车成本=op / max(out, 1),
                延期台月=sum(v["bl"][(m,t)].value() for m in d["models"] for t in T[:-1]),
                流失台=sum(var.value() for var in v["short"].values()),
                加班h=sum(r["ot_hours"] for r in plan), 超限加班h=sum(r["ot_excess_hours"] for r in plan),
                平均缓存=sum(r["buffer_end"] for r in plan) / len(T),
                停线车间月=sum(1 for r in plan if r["shifts"] == 0),
                人数最大月波动=max(sw) if sw else 0.0, 人数变化合计=tot,
                最大月末积压=max((sum(v["bl"][(m,t)].value() for m in d["models"]) for t in T[:-1]), default=0.0))

def selfcheck(d, v, obj, tol=1.0):
    """v4 守恒自检：返回问题列表（空 = 通过）"""
    S, M, T = d["shops"], d["models"], d["months"]; err = []
    tot = sum((pulp.value(e) or 0.0) for e in v["acc"].values())
    if abs(tot - obj) > tol: err.append(f"科目合计 {tot:.0f} ≠ 目标 {obj:.0f}")
    for s in S:
        for t in T:
            n = sum(round(var.value()) for (ss,i,k,tt), var in v["y"].items() if ss == s and tt == t)
            if n != 1: err.append(f"{s}-{t} 选中方案数 {n}")
    for a, b in zip(S[:-1], S[1:]):
        for m in M:
            for t in T:
                prev = v["inv"][(a,m,t-1)].value() if t > T[0] else 0
                if abs(prev + v["x"][(a,m,t)].value() - v["x"][(b,m,t)].value() - v["inv"][(a,m,t)].value()) > 1e-3:
                    err.append(f"流平衡 {a}-{m}-{t}")
        for t in T:
            if sum(v["inv"][(a,m,t)].value() for m in M) > cf.buffer_cap(d, a) + 1e-3: err.append(f"缓存超限 {a}-{t}")
    dem = sum(d["demand"].values())
    deliv = sum((v["ship"] or {}).get((m,t)).value() if v.get("ship") else v["x"][(S[-1],m,t)].value() for m in M for t in T)
    lost = sum(var.value() for var in v["short"].values())
    if abs(deliv + lost - dem) > 1e-2: err.append(f"需求守恒 交付{deliv:.0f}+流失{lost:.0f}≠需求{dem:.0f}")
    return err

ACC_CATEGORIES = ("料", "工", "费", "物流", "资金/其他")
ACCOUNT_MAP = [   # 模型科目 → 财务科目建议 → 口径说明（⚠ 需财务确认）
    ("科目", "类别", "财务科目建议", "口径说明"),
    ("停工日人工节省", "工", "直接人工（冲减）", "v5.2 ⚠ 停工日 × 日工资 × 可省比例（派遣比、停工日发薪%）；负数"),
    ("停工日能源节省", "费", "燃料动力（冲减）", "v5.2 ⚠ 停 1 天省的运行能耗 − 增加的待机/保温；负数"),
    ("借调节省人工", "工", "直接人工（冲减）", "v5.2 ⚠ 借入车间少雇的人 × 月薪；负数"),
    ("借调占用(借出方停工日不能省)", "工", "直接人工", "v5.2 ⚠ 借出方停工日的人去支援，不能按停工日省"),
    ("JPH换档", "费", "制造费用-工程/验证", "v5.2 ⚠ 每次换档 30 万元（线平衡+验证）；损失 2 天产出走产能约束"),
    ("复产质量", "费", "制造费用-质量成本", "停工日所在的车间月计一次。默认 0，不进模型。⚠"),
    ("起订加急", "物流", "采购-加急费", "首车间产量月环比超过 10% 的月份一笔。默认 0，不进模型。⚠"),
    ("物料",       "料", "直接材料",              "BOM × 零件价（月版）；缺料走 supply 约束；只做口径不进目标"),
    ("人工",       "工", "直接人工（含间接人工、夜班补贴）", "(直接+间接定员) × 班次 × 工资 + 夜班定员 × 夜班数 × 天数 × 元/人/夜班（v4：两班、三班均计）"),
    ("停线固定",   "费", "制造费用-停线期间费用",  "0 班（整月停线）月固定费：基础能耗/待岗等（⚠ 示例）"),
    ("超限加班溢价", "工", "制造费用-加班费",      "超过 36h/人 的加班小时 × 班组人数 × 溢价（⚠ 示例）"),
    ("延期成本",   "资金/其他", "（决策用，非会计科目）", "月末积压台数 × 延期成本/台·月（⚠ 示例）"),
    ("福利社保",   "工", "制造费用-福利费/社保",   "= 工资 × (burden_rate − 1)，含五险一金与补充福利"),
    ("加班",       "工", "制造费用-加班费",        "加班小时 × 班组(直接+间接) × (小时工资×倍数) × 福利系数"),
    ("质量成本",   "工", "制造费用-质量成本",      "返修工时成本；无叫料表时再加报废金额。有 line_supply 时报废只增加叫料，不重复计报废金额"),
    ("能源固定",   "费", "制造费用-能源（固定）",  "运行功率 × 开动小时 × 电价；含照明空调待机烘房保温"),
    ("能源变动",   "费", "制造费用-能源（变动）",  "单车能耗 × 产量 × 电价（v5.1：所选班次的分时加权电价）；加班能耗（加班时段电价 + 运行气）并入此科目"),
    ("能源-电(运行)", "费", "制造费用-电费",        "v5.1：运行功率 × 有效开动小时 × 班次加权分时电价"),
    ("能源-电(待机)", "费", "制造费用-电费",        "v5.1：待机功率 × 班内空档/夜间/周末小时 × 该时段电价；停炉时只计基础负荷与电泳保温"),
    ("能源-天然气", "费", "制造费用-燃气费",        "v5.1：运行气 m³/h × 开动小时 + 单车吸热气 + 保温气（或电泳保温气）× 气价"),
    ("启停能耗",   "费", "制造费用-能源（启停）",  "v5.1：启炉次数 × (升温电 × 升温时段电价 + 升温气 × 气价)；只含烘房+喷房"),
    ("需量电费",   "费", "制造费用-基本电费",      "v5.1：同时率 × 运行功率 × 需量电价（元/kW·月），按开线车间合计"),
    ("换型",       "费", "制造费用-换型换色",      "fixed=外生次数；decision=按车型切换；color=按在产颜色切换"),
    ("OH",         "费", "制造费用-折旧/维修/其他", "固定 OH + 产量 × 变动 OH 率"),
    ("班车",       "费", "制造费用/管理费用-班车", "班次数 × 每班月单价（阶梯成本，开班即付）"),
    ("外包",       "费", "制造费用-服务外包",      "班次数 × 每班月单价（劳务/物流/保洁/安保）"),
    ("物流-成品",  "物流", "销售费用-运输费",       "成品发运趟次 × 趟费 + 包车/包列月费（模式混装）"),
    ("物流-入厂",  "物流", "制造费用/采购-入厂物流", "入厂取货趟次 × 趟费 + 包车月费（JIT/循环取货）"),
    ("设备折旧",   "费", "制造费用-折旧费",        "asset.csv 月折旧合计（用则须从 OH 扣除折旧避免重复）"),
    ("模具摊销",   "费", "制造费用-工装摊销",      "tooling.csv 月摊销合计（车型专用，影响新车型决策）"),
    ("碳配额购买", "费", "制造费用-碳排放成本",    "超出免费配额部分 × 碳价（co2_per_unit / carbon_free_quota_month / carbon_price）"),
    ("缓存持有",   "资金/其他", "存货-仓储与损耗",  "在制/缓存台数 × 单位持有成本"),
    ("成品持有",   "资金/其他", "存货-成品车持有",  "成品库存台数 × 单位持有成本"),
    ("库存资金",   "资金/其他", "财务费用-存货资金占用", "在制与成品库存 × 单车价值 × 月资金率"),
    ("线前库存",   "资金/其他", "存货-线前库存",        "叫料与在途形成的线前库存 × 零件价值 × 月资金率；期末不低于安全缓冲"),
    ("保修与碳",   "资金/其他", "预计负债-保修 + 环保成本", "单车计提：保修准备 + 碳成本"),
    ("缺口惩罚(流失)", "资金/其他", "（决策用，非会计科目）", "期末仍未交付（流失）台数 × 单台惩罚"),
    ("边际贡献",   "（收益项）", "主营业务收入 − 变动成本", "交付台数 × margin；配置 margin.csv 后进入目标，替代缺口惩罚"),
]
def write_account_map(path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(ACCOUNT_MAP)
    return path

def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
