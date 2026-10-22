"""v5.1 快速重算：只重跑受影响的部分，并复用参数哈希缓存
用法：
  python3 run_quick.py                         # 基准，自动判断改了什么
  python3 run_quick.py --scenario 旺季冲量       # 场景库 data/scenario_library.csv 里的场景
  python3 run_quick.py --scenario '{"tou_version":"2024"}'   # 直接给旋钮 JSON（例：2024 版电价回测）
  python3 run_quick.py --part monthly|daily|all  # 强制指定范围；--force 忽略缓存
判断规则：比较 data/ 与代码文件的哈希和上次运行的记录（.cache/quick_manifest.json）
  月度相关（需求/日历/JPH/班次/车间/全局参数/模型代码）→ 月度模型
  daily_config.json / daily.py → 按天排产
  能源参数（tou_* / shift_times / shop_energy / energy_config / energy.py）→ 两者都重跑
没改的部分直接读缓存，几秒出结果。输出：output/quick/，并打印与上次结果的差异。"""
import argparse, copy, hashlib, json, os, sys, time
import data_loader as dl, engine as en, report as rp, daily
from scenarios import apply_knobs, load_library
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, "output", "quick"); MAN = os.path.join(H, ".cache", "quick_manifest.json")
MONTHLY = {"demand.csv", "calendar.csv", "capacity_limit.csv", "jph_options.csv", "shift_options.csv", "shop_params.csv", "global_params.csv",
           "scenario_library.csv", "model_builder.py", "cost_functions.py", "report.py", "data_loader.py", "engine.py"}
DAILY = {"daily_config.json", "daily.py"}
BOTH = {"tou_periods.csv", "tou_price.csv", "shift_times.csv", "shop_energy.csv", "energy_config.json", "energy.py"}

def file_hashes():
    fs = {}
    for n in os.listdir(os.path.join(H, "data")): fs[n] = os.path.join(H, "data", n)
    for n in MONTHLY | DAILY | BOTH:
        if n.endswith(".py"): fs[n] = os.path.join(H, n)
    return {n: hashlib.sha1(open(p, "rb").read()).hexdigest()[:12] for n, p in fs.items() if os.path.isfile(p)}

def affected(old, new):
    ch = sorted(n for n in new if old.get(n) != new[n]) + sorted(n for n in old if n not in new)
    parts = set()
    for n in ch:
        if n in BOTH: parts |= {"monthly", "daily"}
        elif n in DAILY: parts.add("daily")
        else: parts.add("monthly")
    return ch, parts

def scenario(base, name):
    if not name or name in ("基准", "base"): return base, "基准"
    if name.strip().startswith("{"): return apply_knobs(base, json.loads(name)), "自定义" + hashlib.sha1(name.encode()).hexdigest()[:6]
    lib = {r["name"]: r["knobs"] for r in load_library()}
    if name not in lib: sys.exit(f"场景库里没有「{name}」，可选：{', '.join(lib)}")
    return apply_knobs(base, lib[name]), name

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--scenario", default=""); ap.add_argument("--part", default="auto"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    man = json.load(open(MAN, encoding="utf-8")) if os.path.exists(MAN) else {"hash": {}, "last": {}}
    new = file_hashes(); ch, parts = affected(man.get("hash", {}), new)
    d, tag = scenario(dl.load(), a.scenario)
    if a.part != "auto": parts = {"monthly", "daily"} if a.part == "all" else {a.part}
    elif not man.get("hash"): parts = {"monthly", "daily"}
    if tag not in man.get("last", {}): parts |= {"monthly", "daily"} if a.part == "auto" else set()
    print(f"改动文件：{', '.join(ch) or '无'}；本次重算：{', '.join(sorted(parts)) or '无（全部读缓存）'}；场景：{tag}")
    last = man.setdefault("last", {}).setdefault(tag, {})
    if "monthly" in parts or a.force:
        r = en.solve_case(copy.deepcopy(d), tag, use_cache=not a.force)
        rp.write_csv(os.path.join(OUT, f"{tag}_月度方案.csv"), r["plan"])
        rp.write_csv(os.path.join(OUT, f"{tag}_月度成本科目.csv"), [{"科目": k, "金额_元": round(x)} for k, x in r["cost"].items()])
        k = dict(运营成本_万元=round(r["kpi"]["运营成本"] / 1e4), 单车_元=round(r["kpi"]["单车成本"]), 延期台月=round(r["kpi"]["延期台月"]),
                 能源_万元=round(sum(x for kk, x in r["cost"].items() if kk.startswith(("能源", "启停", "需量"))) / 1e4))
        print(f"[月度] {'缓存' if r['cached'] else '求解'} {r['solve_seconds']:.1f}s →", k, "｜上次：", last.get("monthly", "—")); last["monthly"] = k
    if "daily" in parts or a.force:
        res, fd = daily.main(use_cache=not a.force, d=d) if tag == "基准" else daily.main(("continuous", "sync", "optimal"), use_cache=not a.force, d=d)
        k = {daily.NAMES[s]: res[s]["kpi"]["运营成本_万元"] for s in res}
        print("[按天] 运营成本(万元)：", k, "｜上次：", last.get("daily", "—")); last["daily"] = k
    man["hash"] = new; os.makedirs(os.path.dirname(MAN), exist_ok=True); json.dump(man, open(MAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成，用时 {time.time() - t0:.1f}s。结果在 output/quick/ 与 output/v5.1/")

if __name__ == "__main__": main()
