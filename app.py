import streamlit as st
import pandas as pd
import requests
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

# ================== 侧边栏 ==================
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

# ================== 改进后的爬取函数（pd.read_html 版） ==================
def fetch_latest_etf_data():
    url = "https://www.sse.com.cn/market/funddata/volumn/etfvolumn/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        
        # 使用 pandas 自动解析页面中的所有表格（解决 JS 加载问题）
        tables = pd.read_html(resp.text)
        if not tables:
            return pd.DataFrame()
        
        # 取第一个表格（即 ETF 规模表）
        table = tables[0].copy()
        
        # 统一列名（不管页面中文列名如何变化，都强制转为标准列）
        if len(table.columns) >= 4:
            table = table.iloc[:, :4]
            table.columns = ["date", "code", "name", "shares"]
            
            # 数据清洗
            table["date"] = pd.to_datetime(table["date"], errors="coerce")
            table["code"] = table["code"].astype(str).str.strip()
            table["name"] = table["name"].astype(str).str.strip()
            table["shares"] = pd.to_numeric(
                table["shares"].astype(str).str.replace(",", "").str.replace(r"[^\d.]", "", regex=True),
                errors="coerce"
            )
            table = table.dropna(subset=["code", "shares"])
            return table
        return pd.DataFrame()
    except Exception as e:
        st.error(f"爬取失败: {str(e)[:100]}")
        return pd.DataFrame()

# ================== 更新按钮 ==================
if st.button("🔄 更新最新数据（所有已添加 ETF）", type="primary"):
    new_df = fetch_latest_etf_data()
    if not new_df.empty:
        new_df = new_df[new_df["code"].isin(st.session_state.tracked)]
        if not new_df.empty:
            df = pd.concat([df, new_df], ignore_index=True).drop_duplicates(subset=["code", "date"])
            st.session_state.data = df
            df.to_csv(DATA_FILE, index=False)
            st.success(f"✅ 成功更新 {len(new_df)} 条最新数据！（最新日期：{new_df['date'].max().date()}）")
            st.rerun()
        else:
            st.warning("今日数据暂未更新或无匹配 ETF")
    else:
        st.warning("未能抓取到表格（交易所页面可能正在更新），请稍后重试或手动导入历史数据")

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

# ================== 主图表（现在即使没有数据也会显示日期选择器） ==================
st.header("📈 每日总份额可视化")

if not st.session_state.tracked:
    st.info("请先在左侧侧边栏添加 ETF")
else:
    selected_codes = st.multiselect("选择要显示的 ETF", 
                                  options=st.session_state.tracked, 
                                  default=st.session_state.tracked[:3])
    
    if selected_codes:
        # 日期选择器始终显示
        col_a, col_b = st.columns(2)
        with col_a:
            start_date = st.date_input("开始日期", value=datetime(2020, 1, 1))
        with col_b:
            end_date = st.date_input("结束日期", value=datetime.today())
        
        plot_df = df[
            (df["code"].isin(selected_codes)) &
            (df["date"] >= pd.Timestamp(start_date)) &
            (df["date"] <= pd.Timestamp(end_date))
        ].copy()
        
        if plot_df.empty:
            st.info("📌 当前选择的 ETF 还没有数据，请点击上方「更新最新数据」按钮或导入历史 CSV")
        else:
            plot_df = plot_df.sort_values(["code", "date"])
            plot_df["ma5"] = plot_df.groupby("code")["shares"].transform(lambda x: x.rolling(5, min_periods=1).mean())
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            for code in selected_codes:
                sub = plot_df[plot_df["code"] == code]
                name = sub["name"].iloc[0] if not sub.empty else code
                
                fig.add_trace(go.Bar(x=sub["date"], y=sub["shares"], name=f"{code} 总份额", marker_color="#1f77b4"), secondary_y=False)
                fig.add_trace(go.Scatter(x=sub["date"], y=sub["ma5"], name=f"{code} 5天均值", line=dict(width=3)), secondary_y=True)
            
            fig.update_layout(
                title="ETF 每日总份额（柱状） + 5天移动平均线",
                xaxis_title="日期",
                yaxis_title="总份额（万份）",
                yaxis2_title="5天均值",
                height=650,
                barmode="group",
                template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("原始数据预览")
            st.dataframe(plot_df[["code", "name", "date", "shares", "ma5"]].round(2), use_container_width=True)

# 自动保存
if not df.empty:
    df.to_csv(DATA_FILE, index=False)

st.divider()
st.caption("💡 提示：\n"
           "• 现在使用 pd.read_html 抓取，更稳健\n"
           "• 首次使用请点击「更新最新数据」获取最新一天份额\n"
           "• 数据会自动保存到 etf_data.csv（云端部署后每次重启可能重置，建议定期导出备份）")
