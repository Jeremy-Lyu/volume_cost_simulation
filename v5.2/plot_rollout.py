"""多工厂复制与推广机制图：核心平台（标准化） + 工厂配置包（本地化） + 单厂上线六步 + 波次推广 + 需求回流（示例结构）"""
import os, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon
import cjkfont; cjkfont.use()
W, H = 30, 21
fig = plt.figure(figsize=(W, H)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
def box(x, y, w, h, title="", body="", fc="white", ec="#455a64", lw=1.4, ls="-", tfs=17, fs=14.5, z=3, tc="#263238", center=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.12", fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))
    if center: ax.text(x+w/2, y+h/2, title, ha="center", va="center", fontsize=tfs, weight="bold", color=tc, zorder=z+1); return
    if title: ax.text(x+w/2, y+h-0.15, title, ha="center", va="top", fontsize=tfs, weight="bold", color=tc, zorder=z+1)
    if body: ax.text(x+w/2, y+h-(0.68 if title else 0.15), body, ha="center", va="top", fontsize=fs, color="#37474f", zorder=z+1, linespacing=1.35)
def arrow(p1, p2, color="#546e7a", lw=2.5, ls="-", rad=0.0, lab="", lx=None, ly=None, z=7):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=24, lw=lw, ls=ls, color=color, connectionstyle=f"arc3,rad={rad}", zorder=z))
    if lab: ax.text(lx if lx is not None else (p1[0]+p2[0])/2, ly if ly is not None else (p1[1]+p2[1])/2, lab, fontsize=14.5, color=color, ha="center", va="center",
                    zorder=z+1, bbox=dict(fc="white", ec=color, boxstyle="round,pad=0.25", lw=1.2))
def section(x, y, w, h, fc, ec, title, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.18", fc=fc, ec=ec, lw=2.2, ls=ls, zorder=0))
    ax.text(x+0.25, y+h-0.22, title, ha="left", va="top", fontsize=20, weight="bold", color=ec, zorder=1)

ax.text(W/2, H-0.35, "多工厂复制与推广机制图：核心标准 + 工厂配置包 + 上线六步 + 波次推广 + 需求回流", ha="center", va="top", fontsize=29, weight="bold", color="#263238")
ax.text(W/2, H-1.1, "示例结构，依据《产量成本模型-要素拆解》第 14、16、18、21 节；台州为试点（种子工厂）；波次、工期、就绪度口径均为示例 ⚠ 待确认", ha="center", va="top", fontsize=16, color="#607d8b")

# ---------- A 核心平台（标准化） ----------
BL = "#1565c0"; section(0.3, 10.3, 9.6, 9.1, "#e3f2fd", BL, "A 核心平台（标准化，所有工厂共用）")
core = [("实体框架 / Ontology 定义", "对象 · 关系 · 规则 · 依据\n统一编码：工厂/车间/车型/JPH档/班次/科目"),
        ("参数表标准（schema）", "8 类参数表 · 必填字段 · 取值范围\n版本号 · 生效/失效日期 · 负责人"),
        ("求解模型结构", "MIP：每车间每月选「JPH档×班次」\n车间链长度由配置决定，不写死"),
        ("成本子模块接口", "输入（车间·档·班次·月）→ 各科目成本\n计算方法版本可按工厂配置"),
        ("策略库 / 场景库 / 旋钮", "成本优先·稳定优先·保人力·保交付\n旺季·缺芯·停线·限电…"),
        ("指标口径 · 质量规则 · 适配器框架", "单车成本·利用率·偏差率口径\n规则库 · 源系统适配器模板")]
for i, (t, b) in enumerate(core):
    c, r = i % 2, i // 2
    box(0.6 + c*4.6, 16.5 - r*2.55, 4.4, 2.35, t, b, ec=BL, tfs=16, fs=13.6)
ax.text(5.1, 10.45, "核心版本 core-x.y：统一发布、统一测试（基准场景回归）", ha="center", va="bottom", fontsize=14.5, color=BL, weight="bold")

# ---------- B 工厂配置包（本地化） ----------
GR = "#2e7d32"; section(10.3, 10.3, 9.9, 9.1, "#e8f5e9", GR, "B 工厂配置包（本地化，每厂一份）")
fields = "车间链 / 工艺路线 · JPH 档\n班次模式 · 日历 · 工资/能源费率\n产能上限 · 缓存 · 本地法规/劳动规则\n源系统映射 · 本地场景"
packs = [("台州 TZ（种子 / 试点）", "已上线 · 配置 TZ-cfg-2026.10", "#fffde7", "#f9a825"),
         ("工厂 B（示例）", "上线中 · 车间链 焊装→涂装→总装", "white", GR),
         ("工厂 C / D …（示例）", "待评估 · 就绪度评估中", "white", "#78909c")]
for i, (t, s, fc, ec) in enumerate(packs):
    y = 16.6 - i*2.0
    box(10.6 + i*0.25, y, 5.75, 1.75, t, s, fc=fc, ec=ec, lw=2, tfs=16, fs=13.6)
box(17.25, 12.7, 2.7, 5.65, "每个配置包包含", fields.replace(" · ", "\n").replace("\n\n", "\n"), ec=GR, tfs=15, fs=13.2)
box(10.6, 10.65, 9.35, 1.85, "", "配置驱动：换配置包，不改核心代码（原型：plants/DEMO_B）\nplant_check.py 检查结构/完整性/规则 → 就绪度 L0–L3\n工厂配置版本独立于核心版本：TZ-cfg-x / B-cfg-x", fc="#f1f8e9", ec=GR, fs=13.8)
arrow((9.95, 15.0), (10.55, 15.0), color=BL, lw=3)


# ---------- C 中心团队 + AI 加速 ----------
PK = "#ad1457"; section(20.6, 10.3, 9.1, 9.1, "#fce4ec", PK, "C 组织与 AI 加速", ls="--")
box(20.9, 14.75, 4.25, 3.85, "中心团队 CoE", "AI&Data 组 + 台州种子团队\n核心维护 · 方法论 · 培训认证\n知识库 / 上线手册\n变更评审（CAB）\n推广委员会：定波次、验收", ec=PK, tfs=16, fs=13.4)
box(25.3, 14.75, 4.1, 3.85, "工厂本地团队", "工厂 Owner（计划/排产）\nkey user：IE·HR·能源\n财务·物流·IT 接口人\n维护本厂参数和场景\n提需求、做验收", ec=PK, tfs=16, fs=13.4)
box(20.9, 10.6, 8.5, 3.9, "AI / LLM 加速复制（只提建议，人确认）", "字段映射自动建议：源系统字段 → 标准参数表\n文档 / 合同 / 工艺文件 → 参数候选值\n质量规则自动生成 · 与台州配置做差异分析\n回测偏差解释 · 上线手册问答（RAG）\n小模型迁移：台州训练 → 新厂少量数据微调", ec=PK, tfs=16, fs=13.6)

# ---------- D 单厂上线六步 ----------
OR = "#e65100"; section(0.3, 5.4, 29.4, 4.55, "#fff3e0", OR, "D 单厂上线六步（每步有清单、交付物、验收门）")
steps = [("1 评估与差异分析", "差异清单（与台州比）\n就绪度评估 · 范围"), ("2 数据盘点与映射", "数据源清单 · 字段映射\n适配器 · 缺口清单"),
         ("3 参数配置与校准", "配置包 v0.x\nplant_check 通过"), ("4 历史回测对账", "近 3–6 个月回测\n偏差报告（车间×科目）"),
         ("5 试运行并行", "新旧方式并行 1–2 个月\n差异解释 · 用户培训"), ("6 正式上线", "上线评审 · 移交运维\n纳入月度对账")]
sw = 4.75
for i, (t, b) in enumerate(steps):
    x = 0.65 + i*4.82; y = 5.85
    pts = [(x, y), (x+sw-0.45, y), (x+sw, y+1.45), (x+sw-0.45, y+2.9), (x, y+2.9), (x+0.45, y+1.45)] if i else [(x, y), (x+sw-0.45, y), (x+sw, y+1.45), (x+sw-0.45, y+2.9), (x, y+2.9)]
    ax.add_patch(Polygon(pts, closed=True, fc="white", ec=OR, lw=2, zorder=3))
    ax.text(x+sw/2+0.1, y+2.45, t, ha="center", va="center", fontsize=17, weight="bold", color=OR, zorder=4)
    ax.text(x+sw/2+0.1, y+1.15, b, ha="center", va="center", fontsize=14.2, color="#37474f", zorder=4, linespacing=1.4)
    ax.text(x+sw-0.2, y-0.02, f"门{i+1}", ha="center", va="top", fontsize=13, color="white", weight="bold", zorder=5,
            bbox=dict(fc=OR, ec=OR, boxstyle="round,pad=0.18"))
arrow((15.2, 10.6), (15.2, 8.75), color=GR, lw=3, lab="配置包进入上线流程", lx=17.4, ly=10.05)

# ---------- E 波次推广 ----------
TE = "#00695c"; section(0.3, 0.3, 19.3, 4.45, "#e0f2f1", TE, "E 波次推广（wave plan，示例 ⚠）")
waves = [("W0 台州试点", "跑通全链路\n沉淀核心 + 手册", "#fffde7", "#f9a825"), ("W1 灯塔复制", "1 个结构相近工厂\n验证复制方法", "white", TE),
         ("W2 小批推广", "2–3 个工厂并行\n本地团队主导", "white", TE), ("W3 全面推广", "其余工厂\n中心团队只做支持", "white", TE)]
for i, (t, b, fc, ec) in enumerate(waves):
    x = 0.6 + i*4.75
    box(x, 1.0, 4.3, 2.75, t, b, fc=fc, ec=ec, lw=2, tfs=17, fs=14.5)
    if i < 3: arrow((x+4.33, 2.35), (x+4.72, 2.35), color=TE, lw=3)
ax.text(10.0, 0.48, "每波结束开评审：KPI 达标、问题回流处理完，才开下一波；越往后，每厂工作量越小（复用越多）", ha="center", va="bottom", fontsize=13.8, color=TE)

# ---------- F 需求回流 ----------
PU = "#4527a0"; section(20.0, 0.3, 9.7, 4.45, "#ede7f6", PU, "F 需求回流到核心（变更评审）")
flow = ["工厂需求 /\n问题", "需求池\n分类", "CAB 评审\n通用？本地？", "核心发布\ncore-x.y+1", "各厂回归\n后升级"]
for i, t in enumerate(flow):
    x = 20.25 + i*1.9
    box(x, 1.3, 1.7, 1.95, t, fc="white", ec=PU, tfs=13.2, center=True)
    if i < 4: arrow((x+1.72, 2.27), (x+1.88, 2.27), color=PU, lw=2.2)
ax.text(24.85, 0.5, "通用需求进核心；本厂特有的只改配置包；改公式 = 新方法版本", ha="center", va="bottom", fontsize=13.2, color=PU)

# 跨区反馈箭头
arrow((24.0, 5.35), (24.0, 4.8), color=PU, lw=2.5)
ax.text(24.3, 5.07, "上线中发现的问题 → 回流", ha="left", va="center", fontsize=13.5, color=PU, zorder=8)
ax.text(5.1, 10.95, "新核心版本由 F 变更评审发布，各厂回归后升级", ha="center", va="bottom", fontsize=13.5, color=PU, zorder=8)
arrow((7.0, 5.35), (7.0, 4.8), color=TE, lw=2.5)
ax.text(7.3, 5.07, "按波次排期", ha="left", va="center", fontsize=13.5, color=TE, zorder=8)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "多工厂复制机制图.png")
plt.savefig(out, dpi=90, bbox_inches="tight", pad_inches=0.2); print("ok", out)
