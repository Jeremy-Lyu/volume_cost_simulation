"""策略对比图（示例数据）"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import csv, os, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cjkfont; cjkfont.use()
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); rd = lambda f: list(csv.DictReader(open(os.path.join(H, "output", f), encoding="utf-8-sig")))
S = rd("strategy_summary.csv"); M = rd("montecarlo_summary.csv")
fig, ax = plt.subplots(1, 3, figsize=(19, 6.2), gridspec_kw={"width_ratios": [2.2, 1.2, 1.2]})
lab = [r["策略"].replace("压力:", "压力\n").replace("(", "\n(") for r in S]
a = [float(r["不含惩罚成本_万元"]) for r in S]; p = [float(r["缺口惩罚_万元"]) for r in S]
c = ["#1976d2", "#388e3c", "#f57c00", "#9e9e9e", "#7b1fa2"]
ax[0].bar(lab, a, color=c, label="运营成本"); ax[0].bar(lab, p, bottom=a, color="#e57373", label="缺口惩罚")
for i, r in enumerate(S):
    ax[0].text(i, a[i]+p[i]+250, f"{int(float(r['总成本_万元'])):,}万\n单车{int(float(r['单车_元'])):,}元\n缺口{r['缺口']}台", ha="center", fontsize=10)
ax[0].set_ylim(38000, 53500); ax[0].set_ylabel("全年总成本（万元）"); ax[0].legend(loc="upper left"); ax[0].set_title("策略对比（示例数据）", fontsize=14)
ax[0].tick_params(axis="x", labelsize=10)
x = range(len(S)); ax[1].bar(x, [float(r["平均利用率"].rstrip("%")) for r in S], color=c)
ax[1].set_xticks(list(x)); ax[1].set_xticklabels(["成本", "稳定", "保人力", "压力\n低惩罚", "压力\n保交付"]); ax[1].set_ylim(80, 101)
ax[1].set_title("平均产能利用率 %", fontsize=14)
for i, r in enumerate(S): ax[1].text(i, float(r["平均利用率"].rstrip("%"))+0.3, r["平均利用率"], ha="center", fontsize=10)
n = [r["方案"] for r in M]; mc = [float(r["平均成本_万元"]) for r in M]; sh = [float(r["平均缺口"]) for r in M]
ax[2].bar(n, mc, color=["#1976d2", "#388e3c"]); ax[2].set_ylim(40000, 46500); ax[2].set_ylabel("平均成本（万元，不含惩罚）")
for i, r in enumerate(M): ax[2].text(i, mc[i]+80, f"{int(mc[i]):,}万\nP90 {int(float(r['P90成本_万元'])):,}万\n平均缺口{int(sh[i])}台\n有缺口{r['有缺口样本占比']}", ha="center", fontsize=10)
ax[2].set_title(f"蒙特卡洛：需求±8% × {M[0]['样本数']} 次", fontsize=14)
plt.tight_layout(); plt.savefig(os.path.join(H, "output", "策略对比.png"), dpi=110); print("ok")
