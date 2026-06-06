import streamlit as st
import pandas as pd
import plotly.express as px
import yaml
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader
from pathlib import Path

st.set_page_config(
    page_title="超市銷售儀表板",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 載入帳號設定（Streamlit Cloud 用 st.secrets，本機用 config.yaml）──────────
def load_config():
    if "credentials" in st.secrets:
        return st.secrets.to_dict()
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        st.error("找不到帳號設定。請在 Streamlit Cloud → App settings → Secrets 填入帳號資訊。")
        st.stop()
    with open(config_path, encoding="utf-8") as f:
        return yaml.load(f, Loader=SafeLoader)

config = load_config()

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

# ── 登入介面 ──────────────────────────────────────────────────────────────────
authenticator.login()

auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error("帳號或密碼錯誤，請重試。")
    st.stop()

if auth_status is None:
    st.warning("請輸入帳號與密碼。")
    st.stop()

# ── 已登入：顯示儀表板 ────────────────────────────────────────────────────────
user_name = st.session_state.get("name", "使用者")

# ── 載入資料 ──────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_csv(Path(__file__).parent / "data" / "supermarket_sales.csv")
    df["Date"] = pd.to_datetime(df["Date"])
    return df

df_all = load_data()

# ── 側邊欄篩選器 ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🛒 超市銷售儀表板")
    st.caption(f"歡迎，{user_name}")
    authenticator.logout("登出", "sidebar")

    st.divider()
    st.subheader("篩選條件")

    min_date = df_all["Date"].min().date()
    max_date = df_all["Date"].max().date()
    date_range = st.date_input(
        "日期範圍",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    branches = st.multiselect(
        "分店",
        options=["A", "B", "C"],
        default=["A", "B", "C"],
    )

    product_lines = st.multiselect(
        "產品線",
        options=sorted(df_all["Product line"].unique()),
        default=sorted(df_all["Product line"].unique()),
    )

# ── 套用篩選器 ────────────────────────────────────────────────────────────────
if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

df = df_all[
    (df_all["Date"].dt.date >= start_date)
    & (df_all["Date"].dt.date <= end_date)
    & (df_all["Branch"].isin(branches))
    & (df_all["Product line"].isin(product_lines))
].copy()

if df.empty:
    st.warning("目前篩選條件下沒有資料，請調整篩選器。")
    st.stop()

# ── 儀表板標題 ────────────────────────────────────────────────────────────────
st.title("🛒 超市銷售儀表板")
st.caption(f"資料期間：{start_date} ～ {end_date}　｜　共 {len(df):,} 筆交易")

# ── Section 1：KPI 摘要 ───────────────────────────────────────────────────────
st.subheader("📊 整體指標")
col1, col2, col3, col4 = st.columns(4)
col1.metric("總銷售額", f"${df['Total'].sum():,.0f}")
col2.metric("總毛利", f"${df['gross income'].sum():,.0f}")
col3.metric("交易筆數", f"{len(df):,}")
col4.metric("平均顧客評分", f"{df['Rating'].mean():.2f} / 10")

st.divider()

# ── Section 2：各分店銷售 & 產品線排行 ───────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🏪 各分店銷售比較")
    branch_df = (
        df.groupby("Branch")["Total"]
        .sum()
        .reset_index()
        .rename(columns={"Total": "銷售額"})
        .sort_values("銷售額", ascending=False)
    )
    branch_df["分店"] = branch_df["Branch"].map(
        {"A": "A（Yangon）", "B": "B（Mandalay）", "C": "C（Naypyitaw）"}
    )
    fig_branch = px.bar(
        branch_df,
        x="分店",
        y="銷售額",
        color="分店",
        text_auto=".2s",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_branch.update_layout(showlegend=False, margin=dict(t=20))
    st.plotly_chart(fig_branch, use_container_width=True)

with col_right:
    st.subheader("📦 產品線銷售排行")
    product_df = (
        df.groupby("Product line")["Total"]
        .sum()
        .reset_index()
        .rename(columns={"Total": "銷售額"})
        .sort_values("銷售額")
    )
    fig_product = px.bar(
        product_df,
        x="銷售額",
        y="Product line",
        orientation="h",
        text_auto=".2s",
        color="銷售額",
        color_continuous_scale="Blues",
    )
    fig_product.update_layout(
        yaxis_title="",
        coloraxis_showscale=False,
        margin=dict(t=20),
    )
    st.plotly_chart(fig_product, use_container_width=True)

# ── Section 3：每日銷售趨勢 ───────────────────────────────────────────────────
st.subheader("📈 每日銷售趨勢")
daily_df = (
    df.groupby(["Date", "Branch"])["Total"]
    .sum()
    .reset_index()
    .rename(columns={"Total": "銷售額"})
)
fig_trend = px.line(
    daily_df,
    x="Date",
    y="銷售額",
    color="Branch",
    markers=True,
    color_discrete_map={"A": "#1f77b4", "B": "#ff7f0e", "C": "#2ca02c"},
)
fig_trend.update_layout(
    xaxis_title="日期",
    legend_title="分店",
    margin=dict(t=20),
)
st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ── Section 4：付款方式 & 顧客分析 ───────────────────────────────────────────
col_a, col_b, col_c = st.columns(3)

with col_a:
    st.subheader("💳 付款方式")
    pay_df = df["Payment"].value_counts().reset_index()
    pay_df.columns = ["付款方式", "筆數"]
    fig_pay = px.pie(
        pay_df,
        values="筆數",
        names="付款方式",
        color_discrete_sequence=px.colors.qualitative.Pastel,
        hole=0.4,
    )
    fig_pay.update_layout(margin=dict(t=20))
    st.plotly_chart(fig_pay, use_container_width=True)

with col_b:
    st.subheader("👥 顧客類型")
    ctype_df = (
        df.groupby("Customer type")["Total"]
        .sum()
        .reset_index()
        .rename(columns={"Total": "銷售額"})
    )
    fig_ctype = px.bar(
        ctype_df,
        x="Customer type",
        y="銷售額",
        color="Customer type",
        text_auto=".2s",
        color_discrete_sequence=["#636EFA", "#EF553B"],
    )
    fig_ctype.update_layout(showlegend=False, xaxis_title="", margin=dict(t=20))
    st.plotly_chart(fig_ctype, use_container_width=True)

with col_c:
    st.subheader("♀♂ 性別分佈")
    gender_df = (
        df.groupby("Gender")["Total"]
        .sum()
        .reset_index()
        .rename(columns={"Total": "銷售額"})
    )
    fig_gender = px.bar(
        gender_df,
        x="Gender",
        y="銷售額",
        color="Gender",
        text_auto=".2s",
        color_discrete_sequence=["#AB63FA", "#FFA15A"],
    )
    fig_gender.update_layout(showlegend=False, xaxis_title="", margin=dict(t=20))
    st.plotly_chart(fig_gender, use_container_width=True)

# ── Section 5：顧客評分分佈 ───────────────────────────────────────────────────
st.subheader("⭐ 顧客評分分佈")
fig_rating = px.histogram(
    df,
    x="Rating",
    nbins=20,
    color_discrete_sequence=["#1f6aa5"],
    opacity=0.8,
)
fig_rating.update_layout(
    xaxis_title="評分",
    yaxis_title="交易筆數",
    bargap=0.05,
    margin=dict(t=20),
)
st.plotly_chart(fig_rating, use_container_width=True)
