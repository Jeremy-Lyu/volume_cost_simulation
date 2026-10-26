"""价值台账：只有「计入合计=是」且状态不是「未验证」的行才能相加。

不同基准、不同尺度的模拟差额各自一行。这一份示例台账全部不计入合计。
"""
import csv


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def includable(rows):
    out = []
    for row in rows:
        if (row.get("状态") or "") == "未验证":
            continue
        if (row.get("计入合计") or "") != "是":
            continue
        out.append(row)
    return out


def net_sum(rows):
    total = 0.0
    for row in includable(rows):
        total += float(row["净差_万元"])
    return total
