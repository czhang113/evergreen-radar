from __future__ import annotations

import streamlit as st

from radar_engine import fmt_large, load_config, run_scan


ACTION_LABELS = {
    "BUY_ZONE": "买入区",
    "RESEARCH": "研究",
    "WATCH": "观察",
    "HOLD": "持有",
    "NO_BUY": "不追",
    "ERROR": "错误",
}

ACTION_ORDER = {
    "BUY_ZONE": 0,
    "RESEARCH": 1,
    "WATCH": 2,
    "HOLD": 3,
    "NO_BUY": 4,
    "ERROR": 5,
}


def action_badge(action: str) -> str:
    colors = {
        "BUY_ZONE": "#0f7b0f",
        "RESEARCH": "#b26a00",
        "WATCH": "#2457a6",
        "HOLD": "#4a5568",
        "NO_BUY": "#9b1c1c",
        "ERROR": "#7a1fa2",
    }
    label = ACTION_LABELS.get(action, action)
    color = colors.get(action, "#4a5568")
    return (
        f"<span style='background:{color};color:white;"
        "padding:0.18rem 0.48rem;border-radius:0.35rem;"
        f"font-size:0.82rem;font-weight:700'>{label}</span>"
    )


def stat_block(label: str, value: str) -> str:
    return (
        "<div style='min-width:0'>"
        f"<div style='font-size:0.82rem;color:#4a5568'>{label}</div>"
        f"<div style='font-size:1.35rem;font-weight:700;line-height:1.25'>{value}</div>"
        "</div>"
    )


def format_table(df):
    return df.assign(
        动作=df["action"].map(ACTION_LABELS).fillna(df["action"]),
        现价=df["price"].map(lambda x: f"{x:.2f}" if x else "-"),
        MA500=df["ma500"].map(lambda x: f"{x:.2f}" if x else "-"),
        偏离度=df["deviation"].map(lambda x: f"{x:+.1f}%" if x else "-"),
        股息=df["div_yield"].map(lambda x: f"{x:.2f}%" if x else "-"),
        PE=df["pe"].map(lambda x: f"{x:.1f}x" if x else "-"),
        市值=df["market_cap"].map(fmt_large),
        日内净流向=df["money_flow"].map(fmt_large),
    )[
        [
            "symbol",
            "name",
            "group",
            "account",
            "动作",
            "现价",
            "MA500",
            "偏离度",
            "股息",
            "PE",
            "市值",
            "日内净流向",
            "comment",
            "note",
        ]
    ].rename(
        columns={
            "symbol": "代码",
            "name": "名称",
            "group": "分组",
            "account": "账户",
            "comment": "雷达评价",
            "note": "备注",
        }
    )


st.set_page_config(page_title="资产长青雷达", page_icon="📊", layout="wide")

config = load_config()
ttl = int(config.get("app", {}).get("cache_ttl_seconds", 3600))


@st.cache_data(ttl=ttl, show_spinner=False)
def cached_scan():
    return run_scan(config)


st.title(config["app"]["title"])
st.caption(config["app"]["subtitle"])

with st.sidebar:
    st.header("控制台")
    refresh = st.button("刷新数据", use_container_width=True)
    view_mode = st.radio(
        "视图",
        ["今日触发", "全部雷达", "持仓护甲", "观察名单", "错误"],
        index=0,
    )
    st.divider()
    st.caption("MA500 负责提醒你该看了，不负责替你决定该买了。")

if refresh:
    st.cache_data.clear()

with st.spinner("正在抓取市场数据..."):
    df, macro, macro_errors, scanned_at = cached_scan()

st.caption(f"最后扫描：{scanned_at}")

macro_cols = st.columns(4)
macro_cards = [
    ("VIX", macro.get("^VIX", 0), "恐慌温度"),
    ("Brent", macro.get("BZ=F", 0), "油价周期"),
    ("Gold", macro.get("GC=F", 0), "避险/通胀"),
    ("USD/CAD", macro.get("CAD=X", 0), "换汇窗口"),
]

for col, (label, value, help_text) in zip(macro_cols, macro_cards):
    col.metric(label, f"{value:.2f}" if label != "USD/CAD" else f"{value:.4f}", help=help_text)

if macro_errors:
    with st.expander("宏观数据错误"):
        for err in macro_errors:
            st.write(err)

action_rank = df["action"].map(ACTION_ORDER).fillna(9)
df_sorted = df.assign(action_rank=action_rank).sort_values(["action_rank", "deviation"])

if view_mode == "今日触发":
    filtered = df_sorted[df_sorted["action"].isin(["BUY_ZONE", "RESEARCH"])]
elif view_mode == "持仓护甲":
    filtered = df_sorted[df_sorted["symbol"].isin(config.get("user_positions", {}).keys())]
elif view_mode == "观察名单":
    filtered = df_sorted[df_sorted["group"].eq("观察名单")]
elif view_mode == "错误":
    filtered = df_sorted[df_sorted["action"].eq("ERROR")]
else:
    filtered = df_sorted

if filtered.empty:
    st.info("当前没有需要特别处理的标的。")
else:
    st.subheader(view_mode)
    for _, row in filtered.iterrows():
        with st.container(border=True):
            top = st.columns([1.1, 2.2, 1.15, 1.35, 0.8])
            top[0].markdown(f"### {row['symbol']}")
            top[1].markdown(f"**{row['name']}**  \n{row['group']} / {row['account']}")
            top[2].markdown(
                stat_block("现价", f"{row['price']:.2f}" if row["price"] else "-"),
                unsafe_allow_html=True,
            )
            top[3].markdown(
                stat_block("MA500偏离", f"{row['deviation']:+.1f}%" if row["ma500"] else "-"),
                unsafe_allow_html=True,
            )
            top[4].markdown(action_badge(row["action"]), unsafe_allow_html=True)
            st.write(row["comment"])
            if row["note"]:
                st.caption(row["note"])
            if row["error"]:
                st.error(row["error"])

st.divider()
st.subheader("完整表格")
st.dataframe(format_table(df_sorted), use_container_width=True, hide_index=True)

st.caption("规则提醒：偏离度触发只解决“何时看”，买前仍需确认护城河、估值和最新财报。")
