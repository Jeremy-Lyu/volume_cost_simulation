"""内网工作台。在 v5.2 目录执行：streamlit run workbench/app.py"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import streamlit as st
import workbench.api as api
import workbench.ask as ask

st.set_page_config(page_title="产量成本工作台", layout="wide")
if "results" not in st.session_state:
    st.session_state.results = []
if "knobs" not in st.session_state:
    st.session_state.knobs = {}
if "question" not in st.session_state:
    st.session_state.question = ""
if "name" not in st.session_state:
    st.session_state.name = "自定义"
if "chat" not in st.session_state:
    st.session_state.chat = []
if "draft" not in st.session_state:
    st.session_state.draft = None

SHOP_CODE = {"冲压": "STP", "焊装": "BIW", "涂装": "PNT", "总装": "TCF", "全部车间": "ALL"}


def _go(question, knobs, name):
    bad = api.validate(knobs)
    if bad:
        st.error("；".join(bad))
        return
    with st.spinner("正在求解。跑过的组合会直接读缓存。"):
        card = api.run(question, knobs, name, source="网页")
    st.session_state.results = ([card] + [c for c in st.session_state.results if c["结果哈希"] != card["结果哈希"]])[:4]
    st.session_state.last = card


def _show_card(card):
    s, b = card["本次"], card["基准"]
    delta = s["运营成本_万元"] - b["运营成本_万元"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("运营成本", f"{s['运营成本_万元']:,} 万", f"{delta:+,} 万")
    c2.metric("单车", f"{s['单车_元']:,} 元")
    c3.metric("延期 / 流失", f"{s['延期台月']} / {s['流失台']}")
    c4.metric("加班 / 能源", f"{s['加班_万元']} / {s['能源_万元']} 万")
    st.markdown(card["正文"])


st.title("产量成本工作台")
st.caption("示例数据。配置包里的正式表不会被改写。金额来自求解器，决策卡上的数字不能手改。")

tab_scene, tab_slider, tab_card, tab_src, tab_ask = st.tabs(["选场景", "滑块", "对比与决策卡", "参数来源", "对话"])

with tab_scene:
    st.subheader("三个例题")
    cols = st.columns(3)
    for col, item in zip(cols, api.EXERCISES):
        with col:
            st.markdown(f"**{item['title']}**")
            st.write(item["question"])
            if st.button("运行", key=f"ex-{item['id']}"):
                knobs, name, _desc = api.exercise_knobs(item)
                st.session_state.knobs = knobs
                st.session_state.question = item["question"]
                st.session_state.name = name
                _go(item["question"], knobs, name)
    st.subheader("预置场景")
    lib = api.library()
    grid = st.columns(2)
    for i, row in enumerate(lib):
        with grid[i % 2]:
            st.markdown(f"**{row['name']}** · {row['category']}")
            st.write(row["description"])
            if st.button("以此运行", key=f"lib-{row['name']}"):
                st.session_state.knobs = row["knobs"]
                st.session_state.question = row["description"]
                st.session_state.name = row["name"]
                _go(row["description"], row["knobs"], row["name"])
    last = st.session_state.get("last")
    if last and last["名称"] != "自定义":
        st.divider()
        _show_card(last)

with tab_slider:
    st.subheader("只改白名单里的旋钮")
    st.caption("JPH 档、定员、制造费用、求解时限不在这里改。预计：没跑过的月度场景大约几十秒，缓存命中几秒内出结果。")
    demand_all = st.slider("全年需求系数", 0.7, 1.3, 1.0, 0.05)
    mcols = st.columns(6)
    months = {}
    for i, m in enumerate(range(1, 13)):
        with mcols[i % 6]:
            months[m] = st.number_input(f"{m} 月系数", 0.5, 1.3, 1.0, 0.05, key=f"m{m}")
    e1, e2, e3 = st.columns(3)
    elec = e1.slider("电价系数", 0.8, 1.5, 1.0, 0.05)
    wage = e2.slider("工资系数", 0.8, 1.5, 1.0, 0.05)
    gas = e3.slider("气价系数", 0.8, 1.5, 1.0, 0.05)
    use_ot = st.checkbox("改加班上限")
    ot = st.slider("加班上限（小时/人·月）", 0, 60, 36, 1, disabled=not use_ot)
    d1, d2, d3 = st.columns(3)
    shop = d1.selectbox("停线车间", list(SHOP_CODE))
    down_m = d2.number_input("停线月份", 1, 12, 6)
    down_d = d3.number_input("停线天数", 0, 10, 0)
    question = st.text_input("这张卡要回答的问题", st.session_state.question or "自定义场景")
    knobs = {}
    if demand_all != 1:
        knobs["demand_all"] = demand_all
    dm = {str(m): round(v, 2) for m, v in months.items() if abs(v - 1) > 1e-9}
    if dm:
        knobs["demand_month"] = dm
    if elec != 1:
        knobs["elec"] = elec
    if wage != 1:
        knobs["wage"] = wage
    if gas != 1:
        knobs["gas"] = gas
    if use_ot:
        knobs["ot"] = ot
    if down_d:
        knobs["down"] = {f"{SHOP_CODE[shop]}|{int(down_m)}": int(down_d)}
    st.code(json.dumps(knobs, ensure_ascii=False, indent=2) or "{}", language="json")
    if st.button("确认运行", type="primary"):
        _go(question, knobs, "自定义")
        st.session_state.knobs = knobs
        st.session_state.question = question
        st.session_state.name = "自定义"
    if st.session_state.get("last") and st.session_state.last["名称"] == "自定义":
        _show_card(st.session_state.last)

with tab_card:
    rows = st.session_state.results
    if not rows:
        st.info("还没有结果。先在「选场景」或「滑块」运行一次。")
    else:
        st.subheader(f"最近 {len(rows)} 次（最多保留 4 次）")
        head = st.columns(len(rows))
        for col, card in zip(head, rows):
            s, b = card["本次"], card["基准"]
            col.metric(card["名称"], f"{s['运营成本_万元']:,} 万", f"{s['运营成本_万元'] - b['运营成本_万元']:+,} 万")
        pick = st.selectbox("看哪一张卡", [c["名称"] + " · " + c["结果哈希"] for c in rows])
        card = rows[[c["名称"] + " · " + c["结果哈希"] for c in rows].index(pick)]
        _show_card(card)
        st.download_button("下载决策卡 Markdown", card["正文"], file_name=f"决策卡_{card['名称']}.md")
        st.caption(f"留痕：{api.LOG}")

with tab_src:
    st.subheader("参数从哪来")
    st.caption("只读。改正式参数仍编辑配置包里的 CSV，再跑 plant_check。")
    owner = st.text_input("按负责人筛选", "")
    rows = api.load_source_map()
    if owner.strip():
        rows = [r for r in rows if owner.strip() in (r.get("参数所有者") or "")]
    st.dataframe(rows, width="stretch", hide_index=True)
    st.subheader("尚未确认的假设")
    st.dataframe(api.load_assumptions(), width="stretch", hide_index=True)

with tab_ask:
    st.subheader("先确认，再求解")
    st.caption("问题在本地收成旋钮，不改参数文件。解释里的金额只来自决策卡。")
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.write(msg["text"])
    draft = st.session_state.draft
    if draft and draft.get("status") == "confirm":
        c1, c2 = st.columns(2)
        if c1.button("确认运行", key="ask-go"):
            with st.spinner("正在求解。"):
                card = api.run(draft.get("问题") or draft["说"], draft["旋钮"], draft["名称"], source="对话")
            st.session_state.results = ([card] + [c for c in st.session_state.results if c["结果哈希"] != card["结果哈希"]])[:4]
            st.session_state.last = card
            answer = ask.explain(card)
            ask.log_turn(dict(问题=draft.get("问题"), 旋钮=draft["旋钮"], 名称=draft["名称"], 结果哈希=card["结果哈希"], 动作="运行"))
            st.session_state.chat.append({"role": "assistant", "text": answer})
            st.session_state.draft = None
            st.rerun()
        if c2.button("取消", key="ask-no"):
            st.session_state.chat.append({"role": "assistant", "text": "已取消，没有求解。"})
            st.session_state.draft = None
            st.rerun()
    prompt = st.chat_input("用中文提问")
    if prompt:
        st.session_state.chat.append({"role": "user", "text": prompt})
        draft = ask.parse(prompt, st.session_state.draft)
        ask.log_turn({k: draft.get(k) for k in ("原文", "status", "说", "旋钮", "名称")})
        st.session_state.chat.append({"role": "assistant", "text": draft["说"]})
        st.session_state.draft = draft if draft["status"] == "confirm" or draft.get("缺") else None
        st.rerun()
