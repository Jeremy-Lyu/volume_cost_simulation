"""生成示例数据（示例数据，非真实沃尔沃数据）"""
import csv, os
D = os.path.join(os.path.dirname(__file__), "data")
def w(name, header, rows):
    with open(os.path.join(D, name), "w", newline="", encoding="utf-8") as f:
        c = csv.writer(f); c.writerow(header); c.writerows(rows)
months = range(1, 13)
models = ["V446K", "V451", "V452"]
shops = ["STP", "BIW", "PNT", "TCF"]  # 冲压 焊装 涂装 总装
season = [0.85,0.80,1.00,1.00,1.05,1.05,0.95,0.95,1.05,1.10,1.10,1.10]
base = {"V446K": 4200, "V451": 3300, "V452": 2500}
w("demand.csv", ["month","model","demand"], [[t,m,round(base[m]*season[t-1])] for t in months for m in models])
w("calendar.csv", ["month","workdays"], [[t,d] for t,d in zip(months,[20,16,22,21,20,22,23,22,21,18,22,22])])
caps = {"STP":13000,"BIW":12000,"PNT":12500,"TCF":12000}
mshare = {"V446K":0.5,"V451":0.4,"V452":0.35}
w("capacity_limit.csv", ["shop","model","month","cap"], [[s,m,t,round(caps[s]*mshare[m])] for s in shops for m in models for t in months])
# JPH档：jph, 每班定员, 运行功率kW(开动即耗)
opt = {"STP":[(30,40,900),(40,50,1150),(50,62,1400)],
       "BIW":[(24,180,1500),(30,215,1800),(36,255,2100)],
       "PNT":[(24,90,3500),(30,105,3900),(36,122,4300)],
       "TCF":[(24,300,700),(30,360,850),(36,425,1000)]}
w("jph_options.csv", ["shop","jph","heads_per_shift","run_kw"], [[s,*o] for s in shops for o in opt[s]])
w("shift_options.csv", ["shifts","eff_hours_per_shift","night_allowance_per_head","bus_cost_per_shift_month","outsourcing_per_shift_month"],
  [[1,7.5,0,60000,80000],[2,7.5,0,60000,80000],[3,7.0,800,75000,95000]])
w("shop_params.csv", ["shop","kwh_per_unit","oh_fixed_month","oh_var_per_unit","ot_max_hours_month","buffer_cap","hold_cost_per_unit_month"],
  [["STP",15,1.2e6,120,36,6000,150],["BIW",40,2.0e6,200,36,1500,300],["PNT",120,2.5e6,350,36,800,500],["TCF",30,2.2e6,250,36,0,0]])
w("global_params.csv", ["key","value"], [["wage_per_head_month",9000],["ot_rate_per_head_hour",75],["elec_price",0.75],["shortage_penalty",30000],["solver_time_limit",60]])
print("示例数据已生成:", D)
