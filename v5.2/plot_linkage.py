"""数据关联图：输入主数据/参数 → 中间计算 → 成本 → 优化（示例结构）"""
import os, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import cjkfont; cjkfont.use()
C_IN, C_MID, C_COST, C_OPT = "#e3f2fd", "#fff3e0", "#fce4ec", "#e8f5e9"
N = {  # 名称: (x, y, 颜色, 宽)
 "场景":(1.5,13.6,C_IN), "需求":(1.5,12.6,C_IN), "车型配置":(1.5,11.6,C_IN), "BOM/工时":(1.5,10.4,C_IN), "车间/产线":(1.5,9.4,C_IN),
 "日历":(1.5,8.2,C_IN), "班次":(1.5,7.2,C_IN), "JPH档位":(1.5,6.0,C_IN), "设备":(1.5,5.0,C_IN), "产能上限":(1.5,3.9,C_IN),
 "定员标准":(1.5,2.7,C_IN), "能源参数":(1.5,1.5,C_IN),
 "车型需求组合":(6.3,12.1,C_MID), "车间负荷工时":(6.3,9.9,C_MID), "可用小时\n(开动小时)":(6.3,7.7,C_MID), "人数":(6.3,2.7,C_MID),
 "产能":(10.6,5.5,C_MID), "产量":(14.6,10.0,C_MID), "加班小时":(14.6,5.5,C_MID), "能耗":(14.6,1.5,C_MID),
 "人员单价":(18.3,13.4,C_IN), "班车/外包单价":(18.3,8.9,C_IN), "OH参数":(18.3,6.4,C_IN), "电价":(18.3,3.0,C_IN),
 "人工":(22.0,12.8,C_COST), "加班费":(22.0,11.4,C_COST), "班车":(22.0,9.6,C_COST), "外包":(22.0,8.2,C_COST),
 "OH成本":(22.0,6.4,C_COST), "缓存持有":(22.0,4.9,C_COST), "能源成本":(22.0,2.2,C_COST),
 "总成本\n(+缺口惩罚)":(25.9,9.6,C_OPT), "优化求解\n选 JPH档×班次":(25.9,6.9,C_OPT), "最优方案\n+单车成本":(25.9,4.2,C_OPT)}
W, H = 2.5, 0.68
fig, ax = plt.subplots(figsize=(25, 13.5)); ax.set_xlim(0, 27.5); ax.set_ylim(0.2, 15.4); ax.axis("off")
for x, t in [(1.5,"① 输入：主数据/参数"),(8.5,"② 中间计算"),(14.6,"②' 中间计算"),(18.3,"①' 单价参数"),(22.0,"③ 成本科目"),(25.9,"④ 优化")]:
    ax.text(x, 14.75, t, ha="center", fontsize=16, weight="bold", color="#263238")
for nm, (x, y, c) in N.items():
    ax.add_patch(FancyBboxPatch((x-W/2, y-H/2), W, H, boxstyle="round,pad=0.06", fc=c, ec="#455a64", lw=1.4, zorder=3))
    ax.text(x, y, nm, ha="center", va="center", fontsize=13, zorder=4)
def side(a, b):
    (x1,y1,_),(x2,y2,_) = N[a], N[b]
    if abs(x1-x2) < 0.1: return (x1, y1 - H/2 - 0.08) if y2 < y1 else (x1, y1 + H/2 + 0.08), (x2, y2 + H/2 + 0.08) if y2 < y1 else (x2, y2 - H/2 - 0.08)
    return (x1 + W/2 + 0.08, y1), (x2 - W/2 - 0.08, y2)
def ar(a, b, lab="", f=0.45, rad=0.0, color="#78909c", ls="-", lw=1.3):
    p1, p2 = side(a, b)
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=15, connectionstyle=f"arc3,rad={rad}", lw=lw, ls=ls, color=color, zorder=2))
    if lab:
        ax.text(p1[0]+(p2[0]-p1[0])*f, p1[1]+(p2[1]-p1[1])*f, lab, fontsize=10.5, color="#bf360c", ha="center", va="center", zorder=5,
                bbox=dict(fc="white", ec="#ffccbc", boxstyle="round,pad=0.2"))
E = [("场景","需求","场景ID"), ("需求","车型需求组合","车型编码+月份"), ("车型配置","车型需求组合","车型编码"),
     ("BOM/工时","车间负荷工时","车型+车间编码+生效日期"), ("车间/产线","车间负荷工时","车间编码"), ("车型需求组合","车间负荷工时","车型编码"),
     ("日历","可用小时\n(开动小时)","月份"), ("班次","可用小时\n(开动小时)","班次数"),
     ("JPH档位","产能","车间编码+JPH档",0.35), ("设备","产能","车间编码(开动率)",0.5), ("可用小时\n(开动小时)","产能","",0.5),
     ("车型需求组合","产量","车型编码+月份",0.5), ("产能上限","产量","车间+车型+月份",0.62), ("产能","产量","≤产能",0.5),
     ("定员标准","人数","车间编码+JPH档"), ("班次","人数","×班次数",0.6), ("产能","加班小时","缺口÷JPH",0.5), ("产量","加班小时","",0.5),
     ("能源参数","能耗","车间编码+JPH档",0.4), ("可用小时\n(开动小时)","能耗","开动小时",0.22), ("产量","能耗","单车能耗",0.62), ("加班小时","能耗","",0.5),
     ("人数","人工","",0.5), ("人员单价","人工","生效日期",0.5), ("人员单价","加班费","",0.5), ("加班小时","加班费","",0.5),
     ("班次","班车/外包单价","班次数",0.62), ("班车/外包单价","班车","",0.5), ("班车/外包单价","外包","",0.5),
     ("OH参数","OH成本","车间编码",0.5), ("产量","OH成本","",0.5), ("产量","缓存持有","上下游车间",0.75),
     ("能耗","能源成本","",0.5), ("电价","能源成本","月份",0.5)]
for e in E: ar(e[0], e[1], e[2], e[3] if len(e) > 3 else 0.45)
for c in ["人工","加班费","班车","外包","OH成本","缓存持有","能源成本"]: ar(c, "总成本\n(+缺口惩罚)", color="#ad1457", lw=1.1)
ar("总成本\n(+缺口惩罚)", "优化求解\n选 JPH档×班次", color="#2e7d32", lw=2); ar("优化求解\n选 JPH档×班次", "最优方案\n+单车成本", color="#2e7d32", lw=2)
ax.add_patch(FancyArrowPatch((25.9-W/2-0.1, 6.75), (1.5+W/2+0.1, 6.0), arrowstyle="-|>", mutation_scale=16, connectionstyle="arc3,rad=-0.12", lw=2, ls="--", color="#2e7d32", zorder=1))
ax.text(13.0, 0.55, "绿色虚线：求解器回到 JPH档位/班次，每车间每月选一个「JPH档 × 班次数」组合，再重算全链条，取总成本最低", color="#2e7d32", fontsize=12.5, ha="center")
ax.text(13.0, 14.2, "红框文字 = 关联键（JOIN KEY）；所有参数按「场景ID + 生效日期」取版本；示例结构，非真实系统表名", fontsize=12.5, ha="center", color="#37474f")
plt.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "数据关联图.png"), dpi=100, bbox_inches="tight"); print("ok")
