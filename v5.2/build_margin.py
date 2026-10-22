"""P3a：从售价/物料/汇率/关税/退税构建边际贡献 margin.csv（收入侧口径，P3 战略级）
用法：python3 build_margin.py [配置包]     默认 data/，写到该包 margin.csv
可选输入（缺省为 0/1）：price.csv(model,month,price)、fx.csv(month,fx_factor)、
      tariff.csv(model,tariff_per_unit)、rebate.csv(model,rebate_per_unit)、
      global:export_share（出口占比）、global:exchange_sensitivity（汇率敏感度 ⚠ 需财务确认）
口径：margin = 含税售价折算 − 物料 − 关税 + 出口退税 − 变动物流
      折算 = price × (1 − export_share + export_share × fx_factor)
说明：售价/汇率/退税属收入侧口径，必须由财务给定；模型只用 margin 参与决策"""
import csv, os
import data_loader as dl
H = os.path.dirname(os.path.abspath(__file__))
def _o(base, n):
    p = os.path.join(base, n)
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []
def _num(d, key, dflt=0.0): return float(d["g"].get(key, dflt))
def build(base, fx_override=None, tag=""):
    d = dl.load(base)
    price = {(r["model"], int(r["month"])): float(r["price"]) for r in _o(base, "price.csv")}
    fx = {int(r["month"]): float(r["fx_factor"]) for r in _o(base, "fx.csv")}
    tariff = {r["model"]: float(r["tariff_per_unit"]) for r in _o(base, "tariff.csv")}
    rebate = {r["model"]: float(r["rebate_per_unit"]) for r in _o(base, "rebate.csv")}
    share = _num(d, "export_share", 0.0)          # 出口占比
    sens = _num(d, "exchange_sensitivity", 1.0)   # 汇率敏感度：fx 变动对售价的影响比例
    var_other = _num(d, "var_other_per_unit", 0.0)  # 变动物流等其他变动成本/台
    rows, detail = [], []
    for m in d["models"]:
        for t in [0] + list(d["months"]):
            p = price.get((m, t), price.get((m, 0)))
            if p is None: continue
            f = fx_override if fx_override is not None else fx.get(t, fx.get(0, 1.0))
            adj = p * (1 - share) + p * share * (1 + (f - 1) * sens)   # 出口部分按汇率折算
            mat = 0.0
            matd = {(mm, tt): qq for (mm, tt), qq in d["mat"].items()}
            mat = matd.get((m, t), matd.get((m, 0), 0.0))
            mg = adj - mat - tariff.get(m, 0.0) + rebate.get(m, 0.0) - var_other
            rows.append(dict(model=m, month=t, margin_per_unit=round(mg, 2)))
            detail.append(dict(车型=m, 月=t, 售价=p, 汇率因子=f, 折算售价=round(adj, 1), 物料=mat,
                               关税=tariff.get(m, 0.0), 退税=rebate.get(m, 0.0), 其他变动=var_other,
                               边际贡献=round(mg, 1)))
    with open(os.path.join(base, "margin.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["model", "month", "margin_per_unit"]); w.writeheader(); w.writerows(rows)
    return rows, detail
def main(base="data"):
    rows, detail = build(base)
    print(f"=== 基准 margin（写入 {os.path.join(base,'margin.csv')}）===")
    for r in detail[:6]: print(" ", r)
    shock = [(0.95, "人民币升值5%"), (1.05, "人民币贬值5%")]
    print("\n=== 汇率冲击 ±5%（决策口径敏感度）===")
    for f, lab in shock:
        _, dt = build(base, fx_override=f)
        m0 = {r["车型"]: r["边际贡献"] for r in detail if r["月"] == 0}
        m1 = {r["车型"]: r["边际贡献"] for r in dt if r["月"] == 0}
        print(f"  汇率 {lab}: " + "  ".join(f"{k} {m0[k]:,.0f}→{m1[k]:,.0f}" for k in m0))
        build(base)   # 还原基准
if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "data")