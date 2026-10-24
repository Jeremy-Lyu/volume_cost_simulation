"""生成「全成本口径」示例配置包 plants/FULL_COST/（示例数据，非真实数据）
在示例配置包（data/）基础上启用 R7–R14 全部可选扩展，演示：
  物料 / 福利社保 / 间接人工 / 质量FTT / 爬坡 / 换型换色 / 滑橇缓存 / 发运能力与模式混装 /
  库存资金 / 保修 / 碳成本 / 设备折旧 / 模具摊销
说明：启用 asset.csv 后把 oh_fixed_month 中的折旧扣除，避免重复计（示例按原 OH 的 40% 计）
"""
import csv, json, os, shutil
H = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.join(H, "data"); DST = os.path.join(H, "plants", "FULL_COST")
os.makedirs(DST, exist_ok=True)
rd = lambda n: list(csv.DictReader(open(os.path.join(SRC, n), encoding="utf-8")))
def wr(n, rows):
    with open(os.path.join(DST, n), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
# 0 复制基础包
for n in os.listdir(SRC): shutil.copy(os.path.join(SRC, n), os.path.join(DST, n))
# 1 物料：单车物料费（示例量级 7–9 万/台，一月版价格对所有月生效）
wr("mat_cost.csv", [{"model": m, "month": 0, "cost_per_unit": c} for m, c in
                    [("V446K", 76000.0), ("V451", 82000.0), ("V452", 88000.0)]])
# 2 质量：车间一次合格率（返修占用产线时间 → 有效产能折损）
wr("quality.csv", [{"shop": s, "ftt": f} for s, f in [("STP", 0.995), ("BIW", 0.990), ("PNT", 0.970), ("TCF", 0.985)]])
# 3 爬坡：示例——总装 1/2 月为新车型导入期
wr("ramp.csv", [{"shop": "TCF", "month": 1, "factor": 0.90}, {"shop": "TCF", "month": 2, "factor": 0.95}])
# 4 发运能力：整车发运上限（船期/承运商/车位示例）→ 触发成品库先建库后发（月底冲量与船期错配）
wr("shipping_cap.csv", [{"model": m, "month": 0, "cap": c} for m, c in
                        [("V446K", 4500.0), ("V451", 3450.0), ("V452", 2600.0)]])
# 5 间接人员定员（按 JPH 档，示例）
JP = {"STP": [30, 40, 50], "BIW": [24, 30, 36], "PNT": [24, 30, 36], "TCF": [24, 30, 36]}
IND = {"STP": [10, 12, 14], "BIW": [28, 32, 36], "PNT": [22, 24, 27], "TCF": [44, 48, 54]}
wr("indirect.csv", [{"shop": s, "jph": j, "heads_per_shift": ind}
                    for s in JP for j, ind in zip(JP[s], IND[s])])
# 6 换型换色：涂装按颜色；其余车间用外生次数。2 次是示例，对应原先「车型数−1」，不是工厂确认值
wr("changeover.csv", [{"shop": s, "mode": mode, "setups_per_month": n, "hours_per_setup": h, "cost_per_setup": c}
                      for s, mode, n, h, c in [("STP", "fixed", 2, 0.5, 8000), ("BIW", "fixed", 2, 0.3, 3000),
                                               ("PNT", "color", 0, 0.25, 6000), ("TCF", "fixed", 2, 0.2, 2000)]])
# 6b 返修区（R7 并联）：返修工时需求 ≤ 返修区可用工时；质量成本按台计提
wr("rework.csv", [{"shop": s, "stations": st, "hours_per_unit": h, "cost_per_hour": cr,
                   "scrap_rate": sc, "scrap_cost_per_unit": su}
                  for s, st, h, cr, sc, su in [("STP", 3, 0.4, 60, 0.003, 800),
                                               ("BIW", 2, 0.6, 65, 0.005, 1500),
                                               ("PNT", 1, 0.8, 70, 0.012, 1200),
                                               ("TCF", 2, 0.5, 60, 0.003, 2500)]])
# 6c OEE 时间/性能开动率 + 出勤率（把 avail 拆开）
wr("oee.csv", [{"shop": s, "month": t, "time_rate": tr, "perf_rate": pr}
               for s in ["STP", "BIW", "PNT", "TCF"] for t in range(1, 13)
               for tr, pr in [(0.95 if s != "PNT" else 0.93, 0.97 if s != "PNT" else 0.95)]])
wr("attendance.csv", [{"shop": s, "month": t, "rate": (0.93 if t == 2 else 0.97)}
                      for s in ["STP", "BIW", "PNT", "TCF"] for t in range(1, 13)])
# 7 滑橇/吊具数量（R7）：有效缓存上限 = min(库容, 载体数)
wr("carrier.csv", [{"shop": s, "carriers": c} for s, c in [("STP", 6000), ("BIW", 900.0), ("PNT", 500.0), ("TCF", 0)]])
# 8 物流：成品发运（outbound，模式混装）+ 入厂取货（inbound，循环取货/JIT）
wr("logistics.csv", [{"lane": "成品-干线公路", "mode": "truck", "scope": "outbound", "capacity": 9.0, "cost_per_trip": 4200.0, "fixed_month_cost": 0.0},
                     {"lane": "成品-干线铁路", "mode": "rail", "scope": "outbound", "capacity": 30.0, "cost_per_trip": 9000.0, "fixed_month_cost": 60000.0},
                     {"lane": "入厂-近程循环取货", "mode": "milkrun", "scope": "inbound", "capacity": 11.0, "cost_per_trip": 2300.0, "fixed_month_cost": 250000.0},
                     {"lane": "入厂-远程卡车", "mode": "truck", "scope": "inbound", "capacity": 16.0, "cost_per_trip": 3800.0, "fixed_month_cost": 0.0}])
# 8b 叫料与线前库存、颜色、三厂能力分量、零件原币价格（示例；不配这些表则模型与原先一致）
wr("line_supply.csv", [{"model": m, "month": 0, "calloff_cap": 20000, "git_incoming": 0, "safety_buffer": 80,
                        "opening_stock": 80, "scrap_rate": 0.004, "cancel_rate": 0.25} for m in ["V446K", "V451", "V452"]])
wr("models.csv", [{"model": "V446K", "config_load": "high", "color": "白"},
                  {"model": "V451", "config_load": "low", "color": "黑"},
                  {"model": "V452", "config_load": "low", "color": "黑"}])
wr("color_batch.csv", [{"color": "白", "batch": 400}, {"color": "黑", "batch": 300}])
wr("capacity_component.csv", [{"plant": p, "model": "V446K", "month": 10, "max_orders": c}
                              for p, c in [("PlantA", 5000), ("PlantB", 4800), ("PlantC", 4200)]])
wr("part_price.csv", [{"model": m, "month": 0, "price": px, "currency": cur, "fx_rate": fx}
                      for m, px, cur, fx in [("V446K", 10000, "EUR", 7.6), ("V451", 82000, "CNY", 1), ("V452", 11000, "USD", 8)]])
# 9 设备折旧 + 模具摊销（示例）；并把 OH 里的折旧扣除避免重复计
dep = {"STP": 480000.0, "BIW": 800000.0, "PNT": 1000000.0, "TCF": 880000.0}
wr("asset.csv", [{"shop": s, "monthly_depreciation": v} for s, v in dep.items()])
wr("tooling.csv", [{"model": m, "month": 0, "monthly_amount": a} for m, a in
                   [("V446K", 120000.0), ("V451", 120000.0), ("V452", 200000.0)]])
sp = rd("shop_params.csv")
wr("shop_params.csv", [dict(r, oh_fixed_month=round(float(r["oh_fixed_month"]) - dep[r["shop"]], 1)) for r in sp])
# 10 全局：福利社保 / 库存资金 / 保修 / 碳 / 成品持有；并关闭缺口惩罚（改用边际贡献定价）
g = {r["key"]: r["value"] for r in rd("global_params.csv")}
g.update({"burden_rate": 1.35, "capital_rate_month": 0.006, "warranty_per_unit": 900.0,
          "carbon_cost_per_unit": 0.0, "fg_hold_cost_per_unit_month": 80.0, "shortage_penalty": 0.0,
          "co2_per_unit": 0.9, "carbon_free_quota_month": 4000.0, "carbon_price": 90.0})
wr("global_params.csv", [{"key": k, "value": v} for k, v in g.items()])
# 11 边际贡献（售价 − 物料 − 变动物流，示例 ⚠ 财务口径）：交付一台的利润贡献，替代缺口惩罚
wr("margin.csv", [{"model": m, "month": 0, "margin_per_unit": v} for m, v in
                  [("V446K", 30000.0), ("V451", 26000.0), ("V452", 22000.0)]])
# 11 工厂定义 + 财务口径对照表 + 决策留痕模板
json.dump({"plant_id": "FULL_COST", "plant_name": "全成本口径示例（虚构，示例数据）",
           "shops": ["STP", "BIW", "PNT", "TCF"], "core_version": "core-1.0",
           "config_version": "FULL_COST-cfg-0.1-示例", "owner": "⚠ 待指定（工厂 key user）",
           "note": "在示例配置包基础上启用 v2 可选扩展：物料/福利/间接人工/FTT/爬坡/换型/滑橇/发运/资金/保修/碳/折旧/模具。"
                   "option：启用折旧后 oh_fixed 已扣除折旧部分。"},
          open(os.path.join(DST, "plant.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
import report as rp
os.makedirs(os.path.join(H, "output"), exist_ok=True)
rp.write_account_map(os.path.join(H, "output", "account_map.csv"))
with open(os.path.join(H, "output", "decision_log_template.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["场景ID", "参数版本", "策略", "方案摘要", "理由", "风险", "决策人", "日期"]); w.writeheader()
    w.writerow(dict(场景ID="", 参数版本="", 策略="", 方案摘要="", 理由="", 风险="", 决策人="", 日期=""))
print("ok", DST)
print("注：折旧假设占 OH 40%（示例 ⚠），启用 asset.csv 后已从 oh_fixed_month 扣除")
