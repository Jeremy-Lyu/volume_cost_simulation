"""对任意工厂配置包跑基准测算 + 回测对账（示例）
用法：python3 run_plant.py plants/DEMO_B   （不带参数 = data/ 示例配置包）
步骤：配置包检查(plant_check) → 基准求解 → 若有 actual.csv，按 车间×月 对比测算 vs 实际，偏差超阈值标红
输出：output/plant_<id>_plan.csv、output/plant_<id>_backtest.csv"""
import csv, os, sys
import plant_check as pc, data_loader as dl, engine, report as rp
H = os.path.dirname(os.path.abspath(__file__)); TH = 0.05   # 偏差阈值 5%（示例 ⚠）
def main(base):
    lv = pc.main(base)
    if lv.startswith(("L0", "L1")): print("\n就绪度不足，先补数据"); return
    d = dl.load(base); pid = d["plant"]["plant_id"]
    st, obj, plan, _cost, out, sh, _v = engine.solved(d)
    rp.write_csv(os.path.join(H, "output", f"plant_{pid}_plan.csv"), plan)
    print(f"\n[{pid}] 车间链 {'→'.join(d['shops'])}  状态 {st}  总成本 {obj/1e4:,.0f} 万元  产量 {out:,.0f}  单车 {obj/max(out,1):,.0f} 元  缺口 {sh:.0f}（示例数据）")
    act = os.path.join(base, "actual.csv")
    if os.path.exists(act):
        a = {(r["shop"], int(r["month"])): float(r["volume"]) for r in csv.DictReader(open(act, encoding="utf-8"))}
        rows = []
        for r in plan:
            k = (r["shop"], r["month"])
            if k in a and r["volume"]:
                dev = (a[k] - r["volume"]) / r["volume"]
                rows.append(dict(shop=k[0], month=k[1], 测算=r["volume"], 实际=round(a[k]), 偏差=f"{dev:+.1%}", 超阈值="是" if abs(dev) > TH else ""))
        rp.write_csv(os.path.join(H, "output", f"plant_{pid}_backtest.csv"), rows)
        bad = [r for r in rows if r["超阈值"]]
        print(f"回测对账：{len(rows)} 个 车间×月，超阈值 {len(bad)} 个（阈值 ±{TH:.0%}，示例）")
        for r in bad: print("  ", r)
if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(H, "data"))
