"""文档一致性检查（示例数据）。相对本仓库路径，不依赖本机绝对路径。

用法（在 v5.2/ 下）：
  .venv/bin/python doc_check.py

手册与要素拆解若只有 Word、没有同名 md，对应项会报「缺文件」并跳过内容比对，不算致命，除非你本机另有 md 底稿。
"""
import csv, os, re, sys
import data_loader as dl, cost_functions as cf, energy as E

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
PUB = os.path.join(ROOT, "发布", "手册")
d = dl.load(None)

def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))

def text(p):
    if p.endswith(".md"):
        return open(p, encoding="utf-8").read()
    if p.endswith(".docx"):
        from docx import Document
        doc = Document(p)
        return "\n".join([x.text for x in doc.paragraphs] + [c.text for t in doc.tables for r in t.rows for c in r.cells])
    return ""

summary = os.path.join(H, "output", "scenario_summary.csv")
if not os.path.exists(summary):
    summary = os.path.join(ROOT, "发布", "样例", "scenario_summary.csv")

DOCS = {
    "手册": os.path.join(PUB, "工厂运营理论与计算手册-v5.2.docx"),
    "要素拆解": os.path.join(PUB, "产量成本模型-要素拆解-v5.2.docx"),
    "升级说明": os.path.join(ROOT, "发布", "版本记录", "v5.2升级说明.md"),
    "图表汇编": os.path.join(PUB, "重要图表汇编-v5.2.docx"),
    "CHANGELOG": os.path.join(H, "CHANGELOG.md"),
}

b = {r["场景"]: r for r in rd(summary)}["基准"]
o36 = next(o for o in d["jph"]["BIW"] if o["jph"] == 36)
p36 = next(o for o in d["jph"]["PNT"] if o["jph"] == 36)
p24 = d["jph"]["PNT"][0]
facts = {
    "基准总成本": f'{int(float(b["总成本_万元"])):,}',
    "φ": f"{cf.flex_var_share(d, 'BIW'):.2f}",
    "启炉一次": f"{E.startup_cost(d, 'PNT', 10):,.0f}",
    "焊装停1天人工": f"{cf.stop_day_saving(d, 'BIW', o36, 2, 10)['人工']:,.0f}",
    "涂装停1天人工": f"{cf.stop_day_saving(d, 'PNT', p36, 2, 10)['人工']:,.0f}",
    "1+2班电价": f"{E.shift_price(d, 10, 2):.4f}",
    "临界间隔": f"{E.breakeven_hours(d, 'PNT', p24['kw'], 10):.1f}",
}
rows = []
for name, p in DOCS.items():
    if not os.path.exists(p):
        rows.append((name, "缺文件", p))
        continue
    s = text(p)
    for w in ("吕工", "审阅"):
        n = s.count(w)
        if n:
            rows.append((name, f"禁用词「{w}」", n))
    if name in ("手册", "升级说明"):
        for k in ("基准总成本", "φ", "焊装停1天人工"):
            if facts[k] not in s:
                rows.append((name, f"缺少/不一致：{k}", facts[k]))
    if name == "手册":
        if "临界间隔 **约 " + facts["临界间隔"] not in s and f"约 {facts['临界间隔']}" not in s:
            rows.append((name, "临界间隔与代码不一致", facts["临界间隔"]))
        for bad in ("未分时 ⚠", "模拟器不含基本电费", "天然气未单列", "非开动时段的待机能耗未建"):
            if bad in s:
                rows.append((name, "过时表述残留", bad))
    if name != "CHANGELOG" and re.search(r"（v5\.1 版）", s):
        rows.append((name, "版本标签残留 v5.1 版", ""))
print("事实（代码现算）：", facts)
for r in rows:
    print("问题：", r)
print("检查完成，问题数", len(rows))
sys.exit(1 if rows else 0)
