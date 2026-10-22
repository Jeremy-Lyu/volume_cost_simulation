"""示例图：总装月需求 vs 产能/产量，及成本构成（示例数据）"""
import csv, os, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cjkfont; cjkfont.use()
H = os.path.dirname(os.path.abspath(__file__)); O = os.path.join(H, "output")
rd = lambda f: list(csv.DictReader(open(os.path.join(O if "plan" in f or "cost" in f else H+"/data", f), encoding="utf-8-sig")))
sc = os.environ.get("SCEN", "基准")
plan = [r for r in rd(f"plan_{sc}.csv") if r["shop"] == "TCF"]
dem = {}; [dem.__setitem__(int(r["month"]), dem.get(int(r["month"]), 0) + float(r["demand"])) for r in rd("demand.csv")]
mon = [int(r["month"]) for r in plan]
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
ax[0].bar(mon, [float(r["capacity"]) for r in plan], color="#cfd8dc", label="总装产能(含加班)")
ax[0].plot(mon, [float(r["volume"]) for r in plan], "o-", label="总装产量")
ax[0].plot(mon, [dem[m] for m in mon], "s--", label="需求")
for r in plan: ax[0].text(int(r["month"]), float(r["capacity"]) * 1.01, f"{int(float(r['jph']))}x{r['shifts']}", ha="center", fontsize=8)
ax[0].set_title(f"总装：需求/产能/产量（{sc}，示例数据）"); ax[0].set_xlabel("月"); ax[0].legend(); ax[0].set_xticks(mon)
c = [r for r in rd(f"cost_{sc}.csv") if float(r["金额_元"]) > 0]
ax[1].pie([float(r["金额_元"]) for r in c], labels=[r["科目"] for r in c], autopct="%1.0f%%"); ax[1].set_title("年度成本构成（示例数据）")
plt.tight_layout(); plt.savefig(os.path.join(O, "demo.png"), dpi=120); print("saved output/demo.png")
