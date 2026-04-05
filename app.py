import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="ETF 总份额统计", layout="wide")
st.title("📊 ETF 总份额爬取 + 统计小程序")
st.caption("数据来源：上海证券交易所官网（每日收盘后更新） | 本地存储：etf_data.csv")

# ================== 数据存储 ==================
DATA_FILE = "etf_data.csv"

if "data" not in st.session_state:
    if os.path.exists(DATA_FILE):
        st.session_state.data = pd.read_csv(DATA_FILE, parse_dates=["date"])
    else:
        st.session_state.data = pd.DataFrame(columns=["code", "name", "date", "shares"])

if "tracked" not in st.session_state:
    st.session_state.tracked = st.session_state.data["code"].unique().tolist() if not st.session_state.data.empty else []

df = st.session_state.data

# ================== 侧边栏：统计目录管理 ==================
st.sidebar.header("📋 统计目录")

if st.session_state.tracked:
    for code in st.session_state.tracked:
        name = df[df["code"] == code]["name"].iloc[-1] if len(df[df["code"] == code]) > 0 else "未知"
        col1, col2 = st.sidebar.columns([4, 1])
        col1.write(f"{code} - {name}")
        if col2.button("删除", key=f"del_{code}"):
            st.session_state.tracked = [c for c in st.session_state.tracked if c != code]
            st.rerun()
else:
    st.sidebar.info("暂无 ETF，点击下方添加")

with st.sidebar.expander("➕ 添加 ETF"):
    new_code = st.text_input("ETF 代码（如 510050）", placeholder="510050")
    if st.button("添加"):
        if new_code and new_code not in st.session_state.tracked:
            st.session_state.tracked.append(new_code)
            st.success(f"已添加 {new_code}")
            st.rerun()
        else:
            st.warning("代码已存在或为空")

# ================== 爬取函数 ==================
def fetch_latest_etf_data():
    url = "https://www.sse.com.cn/market/funddata/volumn/etfvolumn/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            return pd.DataFrame()
        rows = table.find_all("tr")[1:]
        data = []
        today = datetime.now().date().strftime("%Y-%m-%d")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 4:
                code = cols[1].text.strip()
                name = cols[2].text.strip()
                shares_str = cols[3].text.strip().replace(",", "")
                try:
                    shares = float(shares_str)
                    data.append({"code": code, "name": name, "date": today, "shares": shares})
                except:
                    pass
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

if st.button("🔄 更新最新数据（所有已添加 ETF）", type="primary"):
    new_df = fetch_latest_etf_data()
    if not new_df.empty:
        new_df = new_df[new_df["code"].isin(st.session_state.tracked)]
        if not new_df.empty:
            df = pd.concat([df, new_df], ignore_index=True).drop_duplicates(subset=["code", "date"])
            st.session_state.data = df
            df.to_csv(DATA_FILE, index=False)
            st.success(f"成功更新 {len(new_df)} 条最新数据！")
            st.rerun()

# ================== 导入导出 ==================
col1, col2 = st.columns(2)
with col1:
    uploaded = st.file_uploader("📥 导入历史数据（CSV）", type="csv")
    if uploaded:
        imported = pd.read_csv(uploaded, parse_dates=["date"])
        st.session_state.data = pd.concat([st.session_state.data, imported]).drop_duplicates(subset=["code", "date"])
        st.session_state.data.to_csv(DATA_FILE, index=False)
        st.success("导入成功！")
        st.rerun()

with col2:
    if not df.empty:
        csv = df.to_csv(index=False).encode()
        st.download_button("📤 导出全部数据", csv, "etf_data.csv", "text/csv")

# ================== 图表 ==================
st.header("📈 每日总份额可视化")

if df.empty or not st.session_state.tracked:
    st.info("请先添加 ETF 并更新数据")
else:
    selected_codes = st.multiselect("选择要显示的 ETF", options=st.session_state.tracked, default=st.session_state.tracked[:3])
    if selected_codes:
        start_date = st.date_input("开始日期", value=datetime(2020, 1, 1))
        end_date = st.date_input("结束日期", value=datetime.today())
        
        plot_df = df[(df["code"].isin(selected_codes)) & 
                     (df["date"] >= pd.Timestamp(start_date)) & 
                     (df["date"] <= pd.Timestamp(end_date))].copy()
        
        if not plot_df.empty:
            plot_df = plot_df.sort_values(["code", "date"])
            plot_df["ma5"] = plot_df.groupby("code")["shares"].transform(lambda x: x.rolling(5, min_periods=1).mean())
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            for code in selected_codes:
                sub = plot_df[plot_df["code"] == code]
                name = sub["name"].iloc[0] if not sub.empty else code
                fig.add_trace(go.Bar(x=sub["date"], y=sub["shares"], name=f"{code} 总份额"), secondary_y=False)
                fig.add_trace(go.Scatter(x=sub["date"], y=sub["ma5"], name=f"{code} 5天均值", line=dict(width=3)), secondary_y=True)
            
            fig.update_layout(title="ETF 每日总份额（柱状） + 5天移动平均线", height=600, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(plot_df[["code", "name", "date", "shares", "ma5"]].round(2))
            
# 自动保存
if not df.empty:
    df.to_csv(DATA_FILE, index=False)
