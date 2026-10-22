"""场景旋钮层：一个场景 = 一条旋钮取值记录，apply_knobs 把它写进参数字典，下游沿关系重算（示例）
旋钮（JSON）：
  demand_all: 0.9               全局需求系数
  demand_month: {"10": 1.25}     按月需求系数
  demand_model: {"V451": 1.1}    按车型需求系数
  demand_cell: {"10|V451": 1.3}  某月某车型
  avail: {"BIW|5": 0.8, "ALL|7": 0.8}   车间开动率系数（ALL=所有车间）
  down: {"BIW|6": 5}             车间停线天数
  supply: {"V451|4": 0.7}        零件供应上限 = 系数 × 当月该车型需求（在需求旋钮之后计算）
  elec: 1.2  wage: 1.05          单价系数
  ot: 24                         加班上限（小时/月，所有车间）
  gas: 1.1                       v5.1 气价系数
  tou_version: "2024"            v5.1 分时电价版本（2024 = 浙发改价格〔2024〕21号，用于历史回测）
  voltage: "10kV"                v5.1 接入电压
  weekend_policy: {"PNT": "hold"}  v5.1 车间周末策略 hold/shutdown/auto
  penalty: 200000                期末流失惩罚（元/台，绝对值）
  penalty_mul: 2                 流失惩罚乘子
  backlog_mul: 2                 延期持有成本乘子
  night_mul: 2                   夜班补贴乘子
  max_shifts: 2                  去掉更高班次（保留 0 班）
  dispatch: 0.5                  全部车间派遣+临时工占比
  stop_pay: 1.0                  正式工停工日发薪比例
  borrow: 0                      跨车间借调上限
  switch_cost: 2000000           JPH 换档一次的成本（元）
  switch_days: 5                 换档损失天数
  buffer: {"ALL": 0.5, "PNT": 0.3}  缓存上限系数，车间键优先于 ALL
  ftt: {"BIW": 0.93, "ALL": 0.95}   一次合格率（绝对）
  oee: {"PNT|10": 0.9, "ALL|6": 0.85}  有效 OEE（无历史表时 time_rate=该值；有表则乘在时间开动率上）
  attendance: {"ALL|2": 0.9}     出勤率（绝对）
  ramp: {"TCF|1": 0.7}           爬坡系数（绝对）
  cap_mul: 1.15                  车型月度产能上限（capacity_limit）乘子。与开动率不同：开动率乘在 JPH 上，这项乘在车型月上限上
  fg_hold: 800                   成品持有成本（元/台·月）。大于 0 即启用成品库，总装可以提前做、以后再发
  no_flex: true                  关闭停工日与借调
  no_switch: true                关闭换档成本与换档损失
  head_up: 0.05                  人数月增幅上限（招聘提前期的粗参数；不写 = 不限制）
  head_dn: 0.15                  人数月降幅上限
  post_switch_eff: 0.85          换档后首月效率，在换档损失天数之外再扣产能。1 = 不额外扣
  pm_days: 2                     计划维修天数，加在工作日最少的那个月
  moq_fee: 500000                冲压产量月环比超过 10% 时，该月一笔加急费（元）
  restart_cost: 50000            某车间某月只要有停工日，计一次复产质量损失（元）
管理约束（禁三班以外的人数/节拍/利用率）不在旋钮里，由 factory_analysis.py 传给 model_builder.build。
人数月增幅若同时由 factory_analysis 传入 build(head_up=...)，以那个参数为准。
"""
import copy, csv, json, os
LIB = os.path.join(os.path.dirname(__file__), "data", "scenario_library.csv")
def _sk(key): a, b = key.split("|"); return a, int(b)
def apply_knobs(base, k):
    d = copy.deepcopy(base); k = k or {}
    for (t, m) in list(d["demand"]):
        f = k.get("demand_all", 1) * k.get("demand_month", {}).get(str(t), 1) * k.get("demand_model", {}).get(m, 1) * k.get("demand_cell", {}).get(f"{t}|{m}", 1)
        d["demand"][(t, m)] *= f
    av = {}
    for key, f in k.get("avail", {}).items():
        s, t = _sk(key)
        for sh in (d["shops"] if s == "ALL" else [s]): av[(sh, t)] = av.get((sh, t), 1) * f
    d["avail"] = av
    d["down"] = {}
    for key, n in k.get("down", {}).items():
        s, t = _sk(key)
        for sh in (d["shops"] if s == "ALL" else [s]): d["down"][(sh, t)] = n
    d["supply"] = {(m, t): f * d["demand"][(t, m)] for m, t in (_sk(x) for x in k.get("supply", {})) for f in [k["supply"][f"{m}|{t}"]]}
    d["g"]["elec_price"] *= k.get("elec", 1); d["g"]["wage_per_head_month"] *= k.get("wage", 1)
    if "gas" in k and "gas_price" in d["g"]: d["g"]["gas_price"] *= k["gas"]
    if d.get("ecfg") is not None:
        for key in ("tou_version", "voltage"):
            if key in k: d["ecfg"][key] = str(k[key])
    for s, pol in k.get("weekend_policy", {}).items():
        if s in d.get("shop_e", {}): d["shop_e"][s]["weekend_policy"] = pol
    if "ot" in k:
        import data_loader as dl; dl.set_ot_cap(d, k["ot"])
    g = d["g"]
    if "penalty" in k: g["shortage_penalty"] = float(k["penalty"])
    if "penalty_mul" in k: g["shortage_penalty"] *= float(k["penalty_mul"])
    if "backlog_mul" in k: g["backlog_cost_per_unit_month"] *= float(k["backlog_mul"])
    if "night_mul" in k: g["night_allowance_per_head_night"] *= float(k["night_mul"])
    if "max_shifts" in k:
        cap = int(k["max_shifts"])
        d["shift"] = {sk: sv for sk, sv in d["shift"].items() if sk == 0 or sk <= cap}
    for s, row in d.get("lflex", {}).items():
        if "dispatch" in k: row["dispatch_share"] = float(k["dispatch"])
        if "stop_pay" in k: row["stopday_pay_regular"] = float(k["stop_pay"])
        if "borrow" in k: row["borrow_limit"] = float(k["borrow"])
    for s, row in d.get("jsw", {}).items():
        if "switch_cost" in k: row["cost_per_switch"] = float(k["switch_cost"])
        if "switch_days" in k: row["lost_days"] = float(k["switch_days"])
    if "buffer" in k:
        spec = k["buffer"]
        if isinstance(spec, (int, float)): spec = {"ALL": spec}
        for s in d["shops"]:
            d["shop"][s]["buffer_cap"] *= float(spec[s] if s in spec else spec.get("ALL", 1))
    if "ftt" in k:
        d.setdefault("qual", {})
        for s, v in k["ftt"].items():
            for sh in (d["shops"] if s == "ALL" else [s]): d["qual"][sh] = float(v)
    if "oee" in k:
        d.setdefault("oee", {})
        for key, v in k["oee"].items():
            s, t = _sk(key)
            for sh in (d["shops"] if s == "ALL" else [s]):
                old = d["oee"].get((sh, t))
                if old: d["oee"][(sh, t)] = {"time_rate": old["time_rate"] * float(v), "perf_rate": old["perf_rate"]}
                else: d["oee"][(sh, t)] = {"time_rate": float(v), "perf_rate": 1.0}
    if "attendance" in k:
        d.setdefault("att", {})
        for key, v in k["attendance"].items():
            s, t = _sk(key)
            for sh in (d["shops"] if s == "ALL" else [s]): d["att"][(sh, t)] = float(v)
    if "ramp" in k:
        d.setdefault("ramp", {})
        for key, v in k["ramp"].items():
            s, t = _sk(key)
            for sh in (d["shops"] if s == "ALL" else [s]): d["ramp"][(sh, t)] = float(v)
    if "cap_mul" in k:
        f = float(k["cap_mul"])
        d["cap"] = {key: v * f for key, v in d["cap"].items()}
    if "fg_hold" in k: d["g"]["fg_hold_cost_per_unit_month"] = float(k["fg_hold"])
    if k.get("no_flex"): d["lflex"] = {}
    if k.get("no_switch"): d["jsw"] = {}
    c = d.setdefault("coarse", {})
    for key in ("head_up", "head_dn", "post_switch_eff", "pm_days", "moq_fee", "restart_cost"):
        if key in k and k[key] not in ("", None):
            c[key] = float(k[key])
    return d
def load_library(path=LIB):
    with open(path, encoding="utf-8") as f:
        return [dict(r, knobs=json.loads(r["knobs"])) for r in csv.DictReader(f)]
