"""一次测算的结果快照。给看板或编排层只读消费，不替代决策卡正文。

字段约定见发布/样例/结果契约.md。本模块不启 HTTP 服务，也不写回 MES。
"""
import datetime
import json
import os

import pack_version
import plant_check

H = os.path.dirname(os.path.abspath(__file__))


def readiness_of(data_dir=None):
    root = data_dir or os.path.join(H, "data")
    return plant_check.readiness(plant_check.check(root)[1])


def from_card(card, data_dir=None):
    """从决策卡字典抽出可发布的快照。金额只来自已求解结果。"""
    cur = card.get("本次") or {}
    base = card.get("基准") or {}
    return dict(
        schema="vcs_run/0.1",
        场景ID=card.get("名称") or "",
        问题=card.get("问题") or "",
        配置版本=card.get("配置版本") or "",
        代码版本=card.get("代码版本") or "",
        参数哈希=card.get("参数哈希") or pack_version.data_hash(data_dir),
        假设开关=card.get("假设开关") or pack_version.assumption_line(data_dir),
        就绪度=card.get("就绪") or readiness_of(data_dir),
        运行时间=card.get("运行时间") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        结果哈希=card.get("结果哈希") or "",
        旋钮=card.get("旋钮") or {},
        基准=dict(
            运营成本_万元=base.get("运营成本_万元"),
            产量=base.get("产量"),
            状态=base.get("状态"),
        ),
        本次=dict(
            运营成本_万元=cur.get("运营成本_万元"),
            单车_元=cur.get("单车_元"),
            产量=cur.get("产量"),
            延期台月=cur.get("延期台月"),
            流失台=cur.get("流失台"),
            状态=cur.get("状态"),
            班次=cur.get("班次") or [],
        ),
        比基准_万元=(None if cur.get("运营成本_万元") is None or base.get("运营成本_万元") is None
                   else cur["运营成本_万元"] - base["运营成本_万元"]),
        口径=card.get("口径") or "",
        精度=card.get("精度") or "",
        上限=card.get("上限") or "",
        翻转=card.get("翻转") or "",
        降级=card.get("降级") or "",
        跨尺度=card.get("跨尺度") or "",
        未验证=card.get("未验证") or [],
        示例数据=True,
        不做=["不替代 MES/APS", "不自动下达排产", "不把模拟差额写成已实现节省"],
    )


def write(card, path, data_dir=None):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    rec = from_card(card, data_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return rec
