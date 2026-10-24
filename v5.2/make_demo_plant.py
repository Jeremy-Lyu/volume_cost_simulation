"""生成一个示例「工厂 B」配置包 plants/DEMO_B/（全部是示例数据，非任何真实工厂）
演示：不改核心代码，只换配置包。和示例配置包的差异：
  - 车间链只有 焊装→涂装→总装（假设冲压件外购）
  - 需求 ×0.6，车型只有 V446K（示例）
  - 工资 ×0.92、电价 0.68（示例）
  - 总装 JPH 档 20/26/32（示例）
  - 加班上限 32h（示例 ⚠ 按当地规则）
  - 附 actual.csv：示例「实际产量」（基准解 ±随机扰动生成，只用来演示回测对账流程）"""
import csv, json, os, random, shutil
H = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.join(H, "data"); DST = os.path.join(H, "plants", "DEMO_B")
os.makedirs(DST, exist_ok=True)
rd = lambda n: list(csv.DictReader(open(os.path.join(SRC, n), encoding="utf-8")))
def wr(n, rows):
    with open(os.path.join(DST, n), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
SH = ["BIW", "PNT", "TCF"]; MODELS = ["V446K"]
wr("demand.csv", [dict(r, demand=round(float(r["demand"]) * 0.6 * 1.6)) for r in rd("demand.csv") if r["model"] in MODELS])
wr("calendar.csv", rd("calendar.csv"))
wr("capacity_limit.csv", [dict(r, cap=round(float(r["cap"]) * 0.8)) for r in rd("capacity_limit.csv") if r["shop"] in SH and r["model"] in MODELS])
jo = [r for r in rd("jph_options.csv") if r["shop"] in SH]
tcf = [r for r in jo if r["shop"] == "TCF"]
for r, j in zip(tcf, [20, 26, 32]): r["jph"] = j; r["heads_per_shift"] = round(float(r["heads_per_shift"]) * 0.85)
wr("jph_options.csv", jo)
wr("shift_options.csv", rd("shift_options.csv"))
wr("shop_params.csv", [dict(r, ot_max_hours_month=32) for r in rd("shop_params.csv") if r["shop"] in SH])
g = {r["key"]: r["value"] for r in rd("global_params.csv")}
g["wage_per_head_month"] = round(float(g["wage_per_head_month"]) * 0.92); g["elec_price"] = 0.68
wr("global_params.csv", [{"key": k, "value": v} for k, v in g.items()])
json.dump({"plant_id": "DEMO_B", "plant_name": "示例工厂B（虚构，示例数据）", "shops": SH,
           "shop_names": {"BIW": "焊装", "PNT": "涂装", "TCF": "总装"}, "core_version": "core-1.0",
           "config_version": "DEMO_B-cfg-0.1-示例", "owner": "⚠ 待指定（工厂 key user）",
           "local_rules": {"冲压": "外购，不建模（示例假设）", "加班上限": "32h/月（示例 ⚠）"},
           "note": "虚构示例工厂，数字为示例数据"}, open(os.path.join(DST, "plant.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("ok", DST)

def make_actual():
    """基准解 → 加 ±3% 扰动（个别月份 +15%）当作示例实际产量，演示回测对账"""
    import data_loader as dl, model_builder as mb, report as rp
    d = dl.load(DST); P, v = mb.build(d); mb.solve(P, d); plan, *_ = rp.extract(d, v)
    random.seed(7); rows = []
    for r in plan:
        f = random.uniform(0.97, 1.03) * (0.85 if (r["shop"], r["month"]) == ("PNT", 8) else 1)
        rows.append(dict(shop=r["shop"], month=r["month"], volume=round(r["volume"] * f)))
    wr("actual.csv", rows); print("actual.csv ok（示例）")
if __name__ == "__main__":
    make_actual()
