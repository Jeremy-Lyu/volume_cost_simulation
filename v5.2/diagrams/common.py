import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cjkfont; cjkfont.use()
def box(ax, x, y, w, h, text, fc="#ffffff", ec="#455a64", fs=11, bold=False, ha="center", lw=1.4, tc="#212121"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.006", fc=fc, ec=ec, lw=lw))
    tx = x + w/2 if ha == "center" else x + 0.006
    ax.text(tx, y + h/2, text, ha=ha, va="center", fontsize=fs, fontweight="bold" if bold else "normal", color=tc, linespacing=1.35)
def arrow(ax, p, q, color="#1565c0", ls="-", lw=2, rad=0.0, ms=18):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=ms, color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))
def tag(ax, x, y, t, fc="#c62828", fs=10):
    ax.text(x, y, t, fontsize=fs, color="white", fontweight="bold", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.25", fc=fc, ec="none"))
