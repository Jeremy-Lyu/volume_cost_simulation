"""v4 golden 基线：关键结果固化，改代码后自动比对（容差 = 0.05% 或 2 万元，取大）"""
import csv, os
H = os.path.dirname(os.path.abspath(__file__)); G = os.path.join(H, "golden.csv")
KEYS = ("总成本_万元", "产量", "缺口", "延期台月")
def check(summ, update=False):
    if update or not os.path.exists(G):
        with open(G, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(("场景",) + KEYS); [w.writerow((r["场景"],) + tuple(r[k] for k in KEYS)) for r in summ]
        print("golden 基线已写入", G); return []
    ref = {r["场景"]: r for r in csv.DictReader(open(G, encoding="utf-8"))}; bad = []
    for r in summ:
        g = ref.get(r["场景"])
        if not g: continue
        for k in KEYS:
            a, b = float(r[k]), float(g[k]); tol = max(abs(b) * 5e-4, 2 if k == "总成本_万元" else 5)
            if abs(a - b) > tol: bad.append(f"{r['场景']}.{k}: {a} vs golden {b}")
    print("golden 比对：", "通过" if not bad else bad); return bad
if __name__ == "__main__":
    import sys; s = list(csv.DictReader(open(os.path.join(H, "output", "scenario_summary.csv"), encoding="utf-8-sig")))
    check(s, update="--update" in sys.argv)
