"""块7-9：人力 / 能源 / 其他成本（OH、班车、外包、加班）的单元成本函数
给定 车间s、JPH档o、班次k、月份t，返回该方案的固定月成本分项（与产量无关部分）

扩展 v2（全部可选，未配置时与原口径逐位一致）：
  质量 FTT     quality.csv        capacity × ftt（返修占用产线时间）
  爬坡         ramp.csv           capacity × ramp（新车型导入期降速）
  换型换色     changeover.csv     hours 扣减换型时间 + 换型费
  间接人员     indirect.csv       间接定员 × 班次
  福利社保     global:burden_rate 工资 × 系数（单列科目）
  物料         mat_cost.csv       var_cost_per_unit 加物料
  库存资金     global:capital_rate_month  在 model_builder 对 inv 计价
  保修与碳     global:warranty_per_unit / carbon_cost_per_unit  单车计提
"""
import energy as en_

def price(d, t=None, k=2):  # 电价。v5.1：启用分时电价时 = k 班的班次加权分时电价；否则 = 基础电价 × 月度系数（v5 口径）
    if en_.active(d): return en_.shift_price(d, t, k)
    return d["g"]["elec_price"] * d.get("elec_month_factor", {}).get(t, 1.0)

def ot_price(d, t=None):    # v5.1：加班电价按加班所在时段（shift_times.csv 加班行）
    return en_.ot_price(d, t) if en_.active(d) else price(d, t)

def ot_energy_per_hour(d, s, o, t=None):   # 线体加班 1 小时的能源：运行电 + 运行气
    g = en_.se(d, s)["gas_run_m3h"] * en_.gas(d) if en_.active(d) else 0.0
    return o["kw"] * ot_price(d, t) + g

def energy_parts(d, s, o, k, t):   # v5.1：能源固定分项（运行电/待机电/天然气/启停能耗/需量电费）
    if k == 0: return {}
    if not en_.active(d): return {"能源固定": o["kw"] * hours(d, k, t, s) * price(d, t)}
    return en_.parts(d, s, o, k, t, hours(d, k, t, s), workdays(d, s, t))[0]

def energy_policy(d, s, o, k, t):  # 报表用：夜间/周末选择 保温 还是 停炉
    return en_.parts(d, s, o, k, t, hours(d, k, t, s), workdays(d, s, t))[1] if en_.active(d) and k else {}

def _pick(mp, m, t):
    """月份精确命中，否则用 month=0 的默认行。"""
    if not mp: return None
    if (m, t) in mp: return mp[(m, t)]
    return mp.get((m, 0))

def line_row(d, m, t):         # 叫料与线前库存参数；无表则 None
    return _pick(d.get("line_supply"), m, t)

def order_cap(d, m, t):        # 三厂能力分量交集后的订单上限
    return _pick(d.get("cap_component"), m, t)

def slot_cap(d, m, t):         # 周计划回写的槽位产量上限
    return _pick(d.get("slot_cap"), m, t)

def changeover_hours(d, s):   # 换型占用产线小时（fixed：外生次数；decision/color：由 st 变量决定）
    if chg_mode(d, s) in ("decision", "color"): return 0.0
    c = d.get("chg", {}).get(s)
    return c.get("setups_per_month", 0.0) * c.get("hours_per_setup", 0.0) if c else 0.0

def changeover_cost(d, s):    # 换型月费用（fixed 模式；decision/color 按切换次数在目标中计）
    if chg_mode(d, s) in ("decision", "color"): return 0.0
    c = d.get("chg", {}).get(s)
    return c.get("setups_per_month", 0.0) * c.get("cost_per_setup", 0.0) if c else 0.0

def hours(d, k, t, s=None):    # 月有效开动小时 = 每班有效小时 × 班次 × (工作日 − 停线天数) − 换型小时
    h = d["shift"][k]["eff_hours_per_shift"] * k * max(d["days"][t] - d.get("down", {}).get((s, t), 0), 0)
    return max(h - changeover_hours(d, s), 0.0)

def ftt(d, s):                 # 一次合格率（返修/报废 → 有效产能折损），默认 1
    return d.get("qual", {}).get(s, d.get("qual", {}).get("ALL", 1.0))

def ramp(d, s, t):             # 爬坡系数（新车型导入期），默认 1
    return d.get("ramp", {}).get((s, t), 1.0)

def oee(d, s, t):              # 设备综合效率：时间开动率 × 性能开动率（oee.csv，默认 1）
    r = d.get("oee", {}).get((s, t))
    return r["time_rate"] * r["perf_rate"] if r else 1.0

def attendance(d, s, t):       # 出勤率：实到/定员（attendance.csv，默认 1）
    return d.get("att", {}).get((s, t), 1.0)

def avail(d, s, t):            # 外部限产/整体开动率（avail.csv 静态 + 场景旋钮 avail）
    return d.get("avail", {}).get((s, t), 1.0) * d.get("avail_file", {}).get((s, t), 1.0)

def use_rework(d): return bool(d.get("rework"))   # 是否启用独立返修区（启用后 FTT 不再折产线产能，避免重复计）

def rwk(d, s): return d.get("rework", {}).get(s)

def output_factor(d, s, t):
    """正常班与加班共用的有效产出系数：限产 × OEE × 出勤 × 爬坡；未启用返修区时再乘 FTT。"""
    f = avail(d, s, t) * oee(d, s, t) * attendance(d, s, t) * ramp(d, s, t)
    return f if use_rework(d) else f * ftt(d, s)

def quality_cost_per_unit(d, s):   # 质量成本/台：返修工时成本。有叫料表时报废已进线前消耗，不再按台叠加报废金额
    r = rwk(d, s)
    if not r: return 0.0
    ng = 1.0 - ftt(d, s)
    scrap = 0.0 if d.get("line_supply") else r["scrap_rate"] * r["scrap_cost_per_unit"]
    return ng * r["hours_per_unit"] * r["cost_per_hour"] + scrap

def capacity(d, s, o, k, t):   # 正常班产能 = JPH × 开动小时 × 有效产出系数
    return o["jph"] * hours(d, k, t, s) * output_factor(d, s, t)

def ot_units(d, s, o, t, ot_hours):   # 加班产量 = JPH × 加班小时 × 与正常班相同的有效产出系数
    return o["jph"] * ot_hours * output_factor(d, s, t)

def rework_capacity_per_shift(d, s):   # 返修区每班可用工时 = 返修工位数（与产线同班次）
    r = rwk(d, s)
    return r["stations"] if r else 0.0

def indirect_heads(d, s, o):   # 间接人员每班定员（班组长/质量/维修/物流等），按 JPH 档取值
    ind = d.get("indirect", {}).get(s)
    return ind.get(o["jph"], 0.0) if ind else 0.0

def workdays(d, s, t):         # 实际开工天数 = 工作日 − 停线天数
    return max(d["days"][t] - d.get("down", {}).get((s, t), 0), 0) if t is not None else 0.0

def night_shifts(d, k):        # v4 规则6：每天夜班个数（两班倒 1 个、三班 1 个，⚠ 暂定，shift_options.csv:night_shifts）
    return d["shift"][k].get("night_shifts", 0.0)

def labor_breakdown(d, s, o, k, t=None):   # 人工：直接+间接(v4 规则7 归人工) / 福利社保 / 夜班补贴
    direct_heads, ind_heads = o["heads"] * k, indirect_heads(d, s, o) * k
    wage = d["g"]["wage_per_head_month"]
    # v4 规则6：夜班补贴 = 夜班班组定员(直接+间接) × 夜班个数 × 开工天数 × 元/人/夜班
    night = (o["heads"] + indirect_heads(d, s, o)) * night_shifts(d, k) * workdays(d, s, t) * d["g"]["night_allowance_per_head_night"]
    return {"直接人工": direct_heads * wage, "间接人工": ind_heads * wage,
            "福利社保": (direct_heads + ind_heads) * wage * (d["g"].get("burden_rate", 1.0) - 1.0),
            "夜班补贴": night}

def labor(d, s, o, k, t=None):  # 人工合计（含夜班补贴与福利）
    return sum(labor_breakdown(d, s, o, k, t).values())

def energy_fixed(d, s, o, k, t):  # 固定能源合计（v5：运行功率 × 开动小时 × 电价；v5.1：分项之和）
    return sum(energy_parts(d, s, o, k, t).values())

def bus(d, s, o, k, t): return d["shift"][k]["bus_cost_per_shift_month"] * k
def outsourcing(d, s, o, k, t): return d["shift"][k]["outsourcing_per_shift_month"] * k

def fixed_breakdown(d, s, o, k, t):
    lb = labor_breakdown(d, s, o, k, t)
    if k == 0:                 # v4 规则3：0 班 = 整月停线，只付停线固定成本（基础能耗/待岗等，⚠ 示例）
        return {"停线固定": d["shop"][s]["idle_fixed_month"]}
    r = {"人工": lb["直接人工"] + lb["间接人工"] + lb["夜班补贴"],   # v4 规则7：间接人工归人工，不再单列
         **energy_parts(d, s, o, k, t), "班车": bus(d, s, o, k, t), "外包": outsourcing(d, s, o, k, t)}
    if lb["福利社保"]: r["福利社保"] = lb["福利社保"]
    if changeover_cost(d, s): r["换型"] = changeover_cost(d, s)
    return r

def ot_rate(d):                # v4 规则5：加班单价 = 小时工资 × 倍数（工作日1.5/休息日2/法定3，默认1.5 ⚠）
    return d["g"]["wage_per_head_month"] / d["g"]["std_hours_month"] * d["g"]["ot_multiplier"]

def ot_heads(d, s, o):         # 一个线体加班小时需要的人数 = 一个班组（直接+间接）
    return o["heads"] + indirect_heads(d, s, o)

def ot_labor_per_hour(d, s, o):          # 线体加班 1 小时的人工费（含福利）
    return ot_heads(d, s, o) * ot_rate(d) * d["g"].get("burden_rate", 1.0)

def ot_excess_per_hour(d, s, o):         # v4 规则4：超 36h/人 部分每线体小时额外溢价（⚠ 示例）
    return ot_heads(d, s, o) * d["g"]["ot_excess_premium_per_head_hour"]

def ot_labor_cost(d, s, o, otv, otx=0.0):
    return (otv + otx) * ot_labor_per_hour(d, s, o) + otx * ot_excess_per_hour(d, s, o)

def ot_cost_per_hour(d, s, o, t=None):    # 加班1小时（36h 内）：班组加班费 + 运行能耗
    return ot_labor_per_hour(d, s, o) + ot_energy_per_hour(d, s, o, t)

def mat_cost(d, m, t=None):    # 单车物料费。有零件价（原币×汇率）时优先，否则用 mat_cost.csv
    px = _pick(d.get("part_price"), m, t)
    if px is not None: return px
    mat = d.get("mat", {})
    return mat.get((m, t), mat.get((m, 0), 0.0)) if mat else 0.0

def margin(d, m, t=None):      # 单车边际贡献 = 售价 − 物料 − 变动物流（⚠ 财务口径）；用于替代缺口惩罚
    mg = d.get("margin", {})
    return mg.get((m, t), mg.get((m, 0), 0.0)) if mg else 0.0

def unit_value(d, m, t=None):  # 单车价值（库存资金计价基准）：以物料为主，缺则 0
    return mat_cost(d, m, t)

def other_per_unit(d):         # 单车计提：保修准备 + 碳成本
    return d["g"].get("warranty_per_unit", 0.0) + d["g"].get("carbon_cost_per_unit", 0.0)

def var_cost_per_unit(d, s, t=None, m=None):  # 变动：单车能耗 + 变动OH + 质量成本 (+保修碳)。物料不进目标，只做口径（见 margin）
    base = sum(v for kk, v in var_parts(d, s, t).items() if kk in ("能源变动", "OH")) + (d["shop"][s]["kwh_per_unit"] * price(d, t) if en_.active(d) else 0.0) + var_gas(d, s)
    extra = (other_per_unit(d) if s == d["shops"][-1] else 0.0) + quality_cost_per_unit(d, s)
    return base if not extra else base + extra

def var_parts(d, s, t):        # v4：单车变动成本按科目拆开（目标与报表共用）
    # v5.1：分时电价下单车电耗的单价随班次变化，由 model_builder 的 ev[s,t] 线性化计入"能源变动"，这里不再计
    r = {"OH": d["shop"][s]["oh_var_per_unit"]} if en_.active(d) else {"能源变动": d["shop"][s]["kwh_per_unit"] * price(d, t), "OH": d["shop"][s]["oh_var_per_unit"]}
    if var_gas(d, s): r["能源-天然气"] = var_gas(d, s)
    if quality_cost_per_unit(d, s): r["质量成本"] = quality_cost_per_unit(d, s)
    if s == d["shops"][-1] and other_per_unit(d): r["保修与碳"] = other_per_unit(d)
    return r

# ===== v5.2：按天人工弹性 + JPH 换档 =====
def lflex(d, s): return d.get("lflex", {}).get(s)
def flex_var_share(d, s):      # 停工日可省的人工比例 = 正式工(1−派遣比)×(1−停工日发薪%) + 派遣×(1−派遣停工日发薪%)
    r = lflex(d, s)
    if not r: return 0.0
    return (1 - r["dispatch_share"]) * (1 - r["stopday_pay_regular"]) + r["dispatch_share"] * (1 - r["stopday_pay_dispatch"])
def paid_days(d, s): return (lflex(d, s) or {}).get("paid_days_month", 21.75)
def cap_per_day(d, s, o, k, t):   # 一个开工日的产能
    return o["jph"] * d["shift"][k]["eff_hours_per_shift"] * k * output_factor(d, s, t) if k else 0.0
def stop_day_saving(d, s, o, k, t):
    """月内多停 1 个工作日能省多少（元）：人工弹性部分 + 夜班补贴 + 能源（开工日能耗 − 停机日能耗）"""
    if not k or not lflex(d, s): return dict(人工=0.0, 能源=0.0)
    heads = (o["heads"] + indirect_heads(d, s, o)) * k
    lab = heads * d["g"]["wage_per_head_month"] * d["g"].get("burden_rate", 1.0) / paid_days(d, s) * flex_var_share(d, s) \
          + (o["heads"] + indirect_heads(d, s, o)) * night_shifts(d, k) * d["g"]["night_allowance_per_head_night"]
    w = workdays(d, s, t); h = hours(d, k, t, s)
    if en_.active(d) and w > 1:
        a = sum(en_.parts(d, s, o, k, t, h, w)[0].values()); b = sum(en_.parts(d, s, o, k, t, h * (w - 1) / w, w - 1)[0].values()); e = a - b
    else: e = o["kw"] * h / max(w, 1) * price(d, t)
    return dict(人工=lab, 能源=e)
def jph_switch(d, s): return d.get("jsw", {}).get(s)

def var_gas(d, s):             # v5.1：单车变动用气（车身吸热）× 气价
    return en_.se(d, s)["gas_m3_per_unit"] * en_.gas(d) if en_.active(d) else 0.0

def co2_per_unit(d):           # 单车碳排放量（吨/台），0 表示不做碳配额
    return d["g"].get("co2_per_unit", 0.0)

def carbon_quota(d):           # 免费碳配额（吨/月），0 表示无免费额度
    return d["g"].get("carbon_free_quota_month", 0.0)

def carbon_price(d):           # 碳价（元/吨）
    return d["g"].get("carbon_price", 0.0)

def use_carbon_quota(d):       # 是否启用碳配额交易（线性化：超配额部分按碳价购买）
    return co2_per_unit(d) > 0 and carbon_price(d) > 0

def chg_mode(d, s):            # fixed=外生次数（非涂装默认）；decision=按车型计切换，知识库确认前不用；color=按颜色批量计切换
    c = d.get("chg", {}).get(s)
    return (c or {}).get("mode", "fixed") if c else None

def ship_cap(d, m, t=None):    # 发运能力上限（整车物流/库容/承运商运力），未配置返回 None
    sh = d.get("ship", {})
    return sh.get((m, t), sh.get((m, 0))) if sh else None

def buffer_cap(d, s):          # 有效缓存上限 = min(台数上限, 滑橇/吊具数量)（R7 物理流转约束）
    base = d["shop"][s]["buffer_cap"]
    c = d.get("carrier", {}).get(s)
    return min(base, c) if c is not None else base

def tooling_monthly(d):        # 模具工装摊销合计（只计求解月份；month=0 视为每月）
    T = set(d["months"]); tl = d.get("tool", {})
    return sum(v for (m, t), v in tl.items() if t in T) + sum(v for (m, t), v in tl.items() if t == 0) * len(T)

def dep_monthly(d):            # 设备折旧月计合计（常数项；用 asset.csv 时须从 OH 扣除折旧避免重复）
    return sum(d.get("dep", {}).values())
