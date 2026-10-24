"""压力测试图（示例数据）"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import csv, os, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cjkfont; cjkfont.use()
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); rd = lambda f: list(csv.DictReader(open(os.path.join(H, "output", f), encoding="utf-8-sig")))
L, S, C = rd("stress_library.csv"), rd("stress_downtime_sweep.csv"), rd("stress_demand_ceiling.csv")
fig, ax = plt.subplots(1, 3, figsize=(20, 6.5), gridspec_kw={"width_ratios": [2.0, 1.2, 1.2]})
n = [r["场景"] for r in L]; op = [float(r["运营成本_万元"]) for r in L]; sh = [float(r.get("缺口", r.get("流失", 0))) for r in L]
ax[0].bar(n, op, color=["#90a4ae"] + ["#1976d2"] * (len(n) - 2) + ["#c62828"])
for i, r in enumerate(L): ax[0].text(i, op[i] + 60, f"{int(op[i]):,}\n缺口{int(sh[i])}\n瓶颈{r['瓶颈车间']}", ha="center", fontsize=9)
ax[0].set_ylim(40000, max(op) * 1.04); ax[0].set_title("场景库：运营成本（万元，不含惩罚）", fontsize=14); ax[0].tick_params(axis="x", rotation=30, labelsize=10)
d = [int(r["停线天数"]) for r in S]
ax[1].bar([x-0.4 for x in d], [float(r["焊装5月产量"]) for r in S], width=0.8, color="#90caf9", label="焊装5月产量(提前备货)")
ax[1].bar([x+0.4 for x in d], [float(r["焊装6月产量"]) for r in S], width=0.8, color="#1976d2", label="焊装6月产量")
ax[1].set_ylim(0, 15500); ax[1].set_xlabel("焊装 6 月停线天数"); ax[1].set_ylabel("产量（台）"); ax[1].set_xticks(d)
b = ax[1].twinx(); b.plot(d, [float(r["焊装6月加班h"]) for r in S], "o-", color="#f57c00", label="6月加班小时"); b.set_ylim(0, max(45, max(float(r["焊装6月加班h"]) for r in S) * 1.15)); b.set_ylabel("加班小时", color="#f57c00")
for x, r in zip(d, S): b.annotate(f"{r['焊装6月方案']}\n总缺口{r.get('缺口', r.get('流失'))}", (x, float(r["焊装6月加班h"])), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8.5)
ax[1].legend(loc="lower left", fontsize=9); b.legend(loc="lower right", fontsize=9)
ax[1].set_title("焊装停线天数扫描", fontsize=14)
f = [float(r["需求系数"]) for r in C]
ax[2].plot(f, [float(r.get("缺口", r.get("流失", 0))) for r in C], "s-", color="#c62828"); ax[2].set_xlabel("全局需求系数"); ax[2].set_ylabel("全年缺口（台）")
for x, r in zip(f, C): ax[2].annotate(r["瓶颈车间"], (x, float(r.get("缺口", r.get("流失", 0)))), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
ax[2].set_title("需求上限（高惩罚 20 万/台）", fontsize=14)
fig.suptitle("压力测试（示例数据）", fontsize=15); plt.tight_layout(); plt.savefig(os.path.join(H, "output", "压力测试.png"), dpi=110); print("ok")
