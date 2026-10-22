"""中文字体：Linux 用 Noto，macOS 用系统里已有的黑体。找不到文件时不中断出图。"""
import os
from matplotlib import font_manager as fm
import matplotlib.pyplot as plt

CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]
BOLD = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
]

def _first(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def use():
    plt.rcParams["axes.unicode_minus"] = False
    path = _first(CANDIDATES)
    if not path:
        return None
    fm.fontManager.addfont(path)
    bold = _first(BOLD)
    if bold and bold != path:
        fm.fontManager.addfont(bold)
    name = fm.FontProperties(fname=path).get_name()
    plt.rcParams["font.family"] = name
    return name
