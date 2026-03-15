import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import yfinance as yf
from google_sheets_loader import load_google_sheet_data

st.set_page_config(page_title="Portfolio Dashboard", layout="wide")
st.markdown("""
    <style>
    html, body, [class*="css"]  {
        font-family: 'IBM Plex Mono', monospace;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("Portfolio Dashboard")

df = load_google_sheet_data(sheet_name="Portfolio YIS")

# Clean tickers
if not df.empty and "Current Position Value" in df.columns and "Ticker" in df.columns:
    tickers = (
        df["Ticker"]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )
    st.write("Tickers being downloaded:", tickers)
    weights = (
        df.set_index("Ticker")["Current Position Value"]
        .astype(float)
    )
    weights = weights / weights.sum()
    # Download 1 year of price data for portfolio and SPY
    prices = yf.download(tickers, period="1y", auto_adjust=True)["Close"]
    spy = yf.download("SPY", period="1y", auto_adjust=True)["Close"]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()
    prices = prices.fillna(method="ffill").fillna(method="bfill")
    spy = spy.fillna(method="ffill").fillna(method="bfill")
    returns = prices.pct_change().dropna()
    weights = weights.reindex(returns.columns)
    if not returns.empty and weights.notnull().all():
        # Portfolio returns
        portfolio_returns = (returns * weights).sum(axis=1)
        portfolio_growth = (1 + portfolio_returns).cumprod()
        # SPY returns and growth
        spy_returns = spy.pct_change().dropna()
        spy_growth = (1 + spy_returns).cumprod()
        # Metrics
        annual_return = portfolio_returns.mean() * 252
        annual_vol = portfolio_returns.std() * np.sqrt(252)
        risk_free = 0.04
        sharpe = (annual_return - risk_free) / annual_vol if annual_vol > 0 else np.nan
        running_max = portfolio_growth.cummax()
        drawdown = portfolio_growth / running_max - 1
        max_drawdown = drawdown.min()
        n_positions = len(weights.dropna())
        # SECTION 1 — Portfolio Summary Metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Annual Return", f"{annual_return:.2%}")
        col2.metric("Volatility", f"{annual_vol:.2%}")
        col3.metric("Sharpe Ratio", f"{sharpe:.2f}")
        col4.metric("Max Drawdown", f"{max_drawdown:.2%}")
        col5.metric("Positions", n_positions)
        # SECTION 2 — Portfolio Growth vs Benchmark
        st.subheader("Portfolio vs Market")
        fig, ax = plt.subplots()
        portfolio_growth.plot(ax=ax, label="Portfolio")
        spy_growth.plot(ax=ax, label="SPY", color="gray", linestyle="--")
        ax.set_title("Portfolio Growth vs SPY")
        ax.set_ylabel("Growth of $1")
        ax.set_xlabel("Date")
        ax.legend()
        st.pyplot(fig)
        # SECTION 3 — Drawdown Chart
        st.subheader("Drawdown")
        fig2, ax2 = plt.subplots()
        ax2.fill_between(drawdown.index, drawdown.values, 0, color="red", alpha=0.3)
        ax2.set_title("Portfolio Drawdown")
        ax2.set_ylabel("Drawdown")
        ax2.set_xlabel("Date")
        st.pyplot(fig2)
        # SECTION 4 — Rolling Sharpe Ratio
        st.subheader("Rolling Sharpe Ratio (60d)")
        rolling_mean = portfolio_returns.rolling(60).mean()
        rolling_std = portfolio_returns.rolling(60).std()
        rolling_sharpe = (rolling_mean / rolling_std) * np.sqrt(252)
        fig3, ax3 = plt.subplots()
        rolling_sharpe.plot(ax=ax3)
        ax3.set_title("60-Day Rolling Sharpe Ratio")
        ax3.set_ylabel("Sharpe Ratio")
        ax3.set_xlabel("Date")
        st.pyplot(fig3)
        # SECTION 5 — Asset Allocation
        st.subheader("Asset Allocation")
        alloc = weights.dropna().sort_values(ascending=True)
        fig4, ax4 = plt.subplots()
        ax4.barh(alloc.index, alloc.values * df["Current Position Value"].sum())
        ax4.set_xlabel("Position Value ($)")
        ax4.set_title("Asset Allocation")
        st.pyplot(fig4)
        # SECTION 6 — Correlation Matrix
        st.subheader("Correlation Matrix")
        corr = returns.corr()
        fig5, ax5 = plt.subplots()
        sns.heatmap(corr, annot=True, cmap="coolwarm", ax=ax5)
        ax5.set_title("Asset Return Correlation")
        st.pyplot(fig5)
        # SECTION 7 — Individual Asset Performance
        st.subheader("Individual Asset Performance")
        indiv_growth = (1 + returns).cumprod()
        fig6, ax6 = plt.subplots()
        indiv_growth.plot(ax=ax6)
        ax6.set_title("Cumulative Return by Asset")
        ax6.set_ylabel("Growth of $1")
        ax6.set_xlabel("Date")
        ax6.legend(loc="best")
        st.pyplot(fig6)
    else:
        st.warning("Portfolio analytics could not be calculated due to missing or incompatible data.")
else:
    st.warning("Not enough data for analytics.")
