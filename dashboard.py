import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from google_sheets_loader import load_google_sheet_data

# ==========================================
# 1. SETUP & CLEAN AESTHETICS
# ==========================================
st.set_page_config(page_title="Portfolio Analytics", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');
    
    html, body, [class*="css"], .stMetric label, button { 
        font-family: 'IBM Plex Mono', monospace !important; 
    }
    [data-testid="stAppViewContainer"] { background-color: #F8FAFC; }
    div[data-testid="stMetric"] { 
        background-color: #FFFFFF; border: 1px solid #E2E8F0; 
        padding: 1.25rem; border-radius: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricValue"] { font-weight: 600; color: #0F172A; }
    </style>
    """, unsafe_allow_html=True)

col_title, col_btn = st.columns([4, 1])
with col_title:
    st.title("PORTFOLIO ANALYTICS")
with col_btn:
    st.write("<br>", unsafe_allow_html=True)
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ==========================================
# 2. FIXED TIMELINE (Since Inception)
# ==========================================
start_date = "2026-02-23"

# ==========================================
# 3. DATA LOADING
# ==========================================
@st.cache_data(ttl=300)
def get_data():
    return load_google_sheet_data(sheet_name="Portfolio YIS")

try:
    df = get_data()
except Exception as e:
    st.error(f"System Error: Could not connect to data source. {e}")
    st.stop()

if not df.empty and "Ticker" in df.columns and "Current Position Value" in df.columns:
    
    df["Current Position Value"] = (
        df["Current Position Value"].astype(str).str.replace(r'[$,\s]', '', regex=True)
    )
    df["Current Position Value"] = pd.to_numeric(df["Current Position Value"], errors="coerce")
    
    df = df.dropna(subset=["Ticker", "Current Position Value"])
    df = df[df["Ticker"].str.strip() != ""]
    df = df[~df["Ticker"].str.lower().isin(["total", "cash", "sum", "portfolio"])]
    
    tickers = df["Ticker"].unique().tolist()
    
    weights_ser = df.groupby("Ticker")["Current Position Value"].sum()
    total_val = weights_ser.sum()
    weights_ser = weights_ser / total_val

    # ==========================================
    # 4. MARKET DATA & CALCULATIONS
    # ==========================================
    with st.spinner('Syncing market data...'):
        data = yf.download(tickers, start=start_date, progress=False)
        spy_data = yf.download("SPY", start=start_date, progress=False)

        prices = data["Close"].ffill().bfill()
        spy = spy_data["Close"].squeeze().ffill().bfill()

    if isinstance(prices, pd.Series): prices = prices.to_frame(name=tickers[0])
    
    returns = prices.pct_change().dropna()
    weights = weights_ser.reindex(returns.columns).fillna(0)
    
    if weights.sum() > 0:
        weights = weights / weights.sum()
    
    if not returns.empty and weights.sum() > 0:
        port_ret = (returns * weights).sum(axis=1)
        
        spy_ret = pd.Series(spy.pct_change().dropna())
        spy_ret = spy_ret.reindex(port_ret.index).fillna(0)
        
        port_cum_ret = (1 + port_ret).cumprod() - 1
        spy_cum_ret = (1 + spy_ret).cumprod() - 1

        period_return = port_cum_ret.iloc[-1] if len(port_cum_ret) > 0 else 0
        spy_period_return = spy_cum_ret.iloc[-1] if len(spy_cum_ret) > 0 else 0

        ann_ret = port_ret.mean() * 252
        ann_vol = port_ret.std() * np.sqrt(252)
        sharpe = (ann_ret - 0.04) / ann_vol if ann_vol > 0 else 0
        
        downside_returns = port_ret[port_ret < 0]
        downside_vol = downside_returns.std() * np.sqrt(252)
        sortino = (ann_ret - 0.04) / downside_vol if downside_vol > 0 else 0
        
        covariance = port_ret.cov(spy_ret)
        variance = spy_ret.var()
        beta = covariance / variance if variance > 0 else 0
        
        running_max = (1 + port_ret).cumprod().cummax()
        drawdown = ((1 + port_ret).cumprod() / running_max) - 1

        # ==========================================
        # 5. DASHBOARD VISUALS & TOOLTIPS
        # ==========================================
        m1, m2, m3 = st.columns(3)
        m1.metric("Total AUM", f"${total_val:,.2f}")
        m2.metric("Return (Since Feb 23)", f"{period_return:.2%}", f"{(period_return - spy_period_return):.2%} vs SPY")
        
        # Tooltip for Beta
        m3.metric(
            "Portfolio Beta", 
            f"{beta:.2f}", 
            "1.0 = Market Average", 
            delta_color="off",
            help="How wild your portfolio swings compared to the market. 1.0 means you move exactly with the S&P 500. 1.2 means you are 20% more volatile. 0.8 means you are 20% less volatile."
        )
        
        st.write("<br>", unsafe_allow_html=True)
        
        m4, m5, m6 = st.columns(3)
        
        # Tooltip for Drawdown
        m4.metric(
            "Max Drawdown", 
            f"{drawdown.min():.2%}",
            help="The biggest percentage drop your portfolio has taken from its highest peak down to its lowest valley. It measures your worst-case loss so far."
        )
        
        # Tooltip for Sharpe
        m5.metric(
            "Sharpe Ratio", 
            f"{sharpe:.2f}",
            help="Measures your return vs. your risk. Are you getting paid enough for the bumpy ride? A higher number is better. Over 1.0 is considered good."
        )
        
        # Tooltip for Sortino
        m6.metric(
            "Sortino Ratio", 
            f"{sortino:.2f}",
            help="Similar to the Sharpe Ratio, but vastly superior for retail investors because it ONLY penalizes you for 'bad' volatility (when your stocks drop in price). Higher is better."
        )

        st.write("<br><br>", unsafe_allow_html=True)

        clean_layout = dict(
            font=dict(family="IBM Plex Mono, monospace", color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=30, b=10),
            hovermode="x unified"
        )

        st.subheader("Performance vs S&P 500 (Since Inception)")
        fig_growth = go.Figure()
        
        fig_growth.add_trace(go.Scatter(
            x=spy_cum_ret.index, y=spy_cum_ret, name="SPY", 
            line=dict(color='#94A3B8', width=2, dash='dot')
        ))
        fig_growth.add_trace(go.Scatter(
            x=port_cum_ret.index, y=port_cum_ret, name="Portfolio", 
            line=dict(color='#2563EB', width=2.5)
        ))
        
        fig_growth.update_layout(
            **clean_layout,
            height=400, 
            yaxis=dict(showgrid=True, gridcolor='#E2E8F0', zeroline=True, zerolinecolor='#CBD5E1', tickformat=".1%"),
            xaxis=dict(showgrid=False, zeroline=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_growth, use_container_width=True)

        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("Asset Allocation")
            alloc_df = (weights * 100).reset_index()
            alloc_df.columns = ["Ticker", "Weight"]
            alloc_df = alloc_df[alloc_df["Weight"] > 0]
            
            # FIXED: Custom color sequence so Plotly doesn't crash
            custom_slate_colors = ['#0F172A', '#1E293B', '#334155', '#475569', '#64748B', '#94A3B8', '#CBD5E1']
            
            fig_donut = px.pie(
                alloc_df, values='Weight', names='Ticker', hole=0.6,
                color_discrete_sequence=custom_slate_colors
            )
            fig_donut.update_traces(textposition='inside', textinfo='percent+label')
            fig_donut.update_layout(**clean_layout, height=350, showlegend=False)
            st.plotly_chart(fig_donut, use_container_width=True)

        with col_right:
            st.subheader("Risk Correlation")
            corr = returns.corr()
            fig_corr = px.imshow(corr, text_auto=".2f", color_continuous_scale='RdBu_r', aspect="auto", zmin=-1, zmax=1)
            fig_corr.update_layout(**clean_layout, height=350, coloraxis_showscale=False)
            st.plotly_chart(fig_corr, use_container_width=True)

    else:
        st.error("Analytics paused: Not enough trading days to calculate metrics yet.")
else:
    st.warning("Data sync paused: Waiting for valid portfolio data from spreadsheet.")