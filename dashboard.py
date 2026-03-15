import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from google_sheets_loader import load_google_sheet_data

# ==========================================
# 1. SETUP & AESTHETICS (Terminal Theme)
# ==========================================
st.set_page_config(page_title="Portfolio Dashboard", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');
    
    html, body, [class*="css"], .stMetric label {
        font-family: 'IBM Plex Mono', monospace !important;
    }
    
    [data-testid="stAppViewContainer"] {
        background-color: #FAFAFA;
    }
    
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E5E5E5;
        padding: 1rem;
        border-radius: 4px;
    }
    div[data-testid="stMetricValue"] {
        font-weight: 600;
        color: #111111;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("PORTFOLIO_ANALYTICS_")
st.caption("SYSTEM.STATUS: ONLINE")
st.markdown("---")

# ==========================================
# 2. DATA LOADING & AGGRESSIVE CLEANING
# ==========================================
@st.cache_data(ttl=600)
def get_data():
    return load_google_sheet_data(sheet_name="Portfolio YIS")

try:
    df = get_data()
except Exception as e:
    st.error(f"ERR: Connection to data source failed. {e}")
    st.stop()

if not df.empty and "Ticker" in df.columns and "Current Position Value" in df.columns:
    
    # SAFEGUARD 1: Strip $, commas, spaces and force to numbers
    df["Current Position Value"] = (
        df["Current Position Value"]
        .astype(str)
        .str.replace(r'[$,\s]', '', regex=True)
    )
    df["Current Position Value"] = pd.to_numeric(df["Current Position Value"], errors="coerce")
    
    # SAFEGUARD 2: Drop any rows where Ticker is blank or Value is NaN
    df = df.dropna(subset=["Ticker", "Current Position Value"])
    df = df[df["Ticker"].str.strip() != ""]
    
    tickers = df["Ticker"].unique().tolist()
    
    # Calculate initial target weights
    weights_ser = df.set_index("Ticker")["Current Position Value"]
    total_val = weights_ser.sum()
    weights_ser = weights_ser / total_val

    # ==========================================
    # 3. MARKET DATA & MATH
    # ==========================================
    with st.spinner('FETCHING_MARKET_DATA...'):
        data = yf.download(tickers, period="1y", auto_adjust=True)
        # SAFEGUARD 3: Forward/Backward fill to handle recent IPOs or halted trading days
        prices = data["Close"].ffill().bfill()
        spy = yf.download("SPY", period="1y", auto_adjust=True)["Close"].ffill().bfill()

    # Handle the annoying yfinance 1-ticker vs multi-ticker formatting difference
    if isinstance(prices, pd.Series): prices = prices.to_frame(name=tickers[0])
    
    returns = prices.pct_change().dropna()
    
    # SAFEGUARD 4: Sync weights to ONLY the tickers that successfully downloaded
    weights = weights_ser.reindex(returns.columns).fillna(0)
    # Re-normalize weights so they equal 100% even if a ticker was dropped
    if weights.sum() > 0:
        weights = weights / weights.sum()
    
    if not returns.empty and weights.sum() > 0:
        port_ret = (returns * weights).sum(axis=1)
        port_growth = (1 + port_ret).cumprod()
        spy_ret = spy.pct_change().dropna()
        spy_growth = (1 + spy_ret).cumprod()

        ann_ret = port_ret.mean() * 252
        ann_vol = port_ret.std() * np.sqrt(252)
        sharpe = (ann_ret - 0.04) / ann_vol if ann_vol > 0 else 0
        drawdown = (port_growth / port_growth.cummax()) - 1

        # ==========================================
        # 4. VISUALIZATION LAYOUT
        # ==========================================
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("1Y_RETURN", f"{ann_ret:.1%}", f"{(ann_ret - spy_ret.mean()*252):.1%} vs SPY")
        m2.metric("SHARPE_RATIO", f"{sharpe:.2f}")
        m3.metric("MAX_DRAWDOWN", f"{drawdown.min():.1%}")
        m4.metric("TOTAL_AUM", f"${total_val:,.0f}")

        # Shared styling for all charts
        mono_layout = dict(
            font=dict(family="IBM Plex Mono, monospace", color="#111111"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=30, b=10),
            hovermode="x unified"
        )

        st.write("<br>", unsafe_allow_html=True)

        # --- Chart 1: Growth ---
        st.subheader("CUMULATIVE_PERFORMANCE")
        fig_growth = go.Figure()
        
        fig_growth.add_trace(go.Scatter(
            x=spy_growth.index, y=spy_growth, name="SPY", 
            line=dict(color='#A0AEC0', width=1.5, dash='dot')
        ))
        fig_growth.add_trace(go.Scatter(
            x=port_growth.index, y=port_growth, name="PORTFOLIO", 
            line=dict(color='#111111', width=2.5)
        ))
        
        fig_growth.update_layout(
            **mono_layout,
            yaxis=dict(showgrid=True, gridcolor='#EEEEEE', gridwidth=1, zeroline=False, tickformat="$.2f"),
            xaxis=dict(showgrid=False, zeroline=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_growth, use_container_width=True)

        # --- Bottom Row: Allocation & Risk ---
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("ASSET_ALLOCATION")
            alloc_df = (weights * 100).reset_index()
            alloc_df.columns = ["Ticker", "Weight"]
            alloc_df = alloc_df[alloc_df["Weight"] > 0].sort_values("Weight")
            
            fig_bar = px.bar(
                alloc_df, x="Weight", y="Ticker", orientation='h',
                text=alloc_df["Weight"].apply(lambda x: f"{x:.1f}%")
            )
            fig_bar.update_traces(
                marker_color='#111111', 
                textposition='outside',
                textfont=dict(family="IBM Plex Mono, monospace", color="#111111")
            )
            fig_bar.update_layout(
                **mono_layout,
                xaxis=dict(showgrid=False, showticklabels=False, title=""),
                yaxis=dict(title="")
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_right:
            st.subheader("CORRELATION_MATRIX")
            corr = returns.corr()
            fig_corr = px.imshow(
                corr, text_auto=".2f", 
                color_continuous_scale='Greys',
                aspect="auto"
            )
            fig_corr.update_layout(**mono_layout, coloraxis_showscale=False)
            st.plotly_chart(fig_corr, use_container_width=True)

    else:
        st.error("SYS.ERR: Analytics failed. Check if Tickers are valid Yahoo Finance symbols.")
else:
    st.warning("SYS.MSG: No valid data found. Check 'Ticker' and 'Current Position Value' columns.")