"""섹터 ETF 스냅샷 + (옵션) 개별 종목 TTM EPS 시계열."""

from datetime import date
from typing import Tuple

import numpy as np
import pandas as pd
import streamlit as st

from src.data.market import closes, get_info, get_prices, get_quarterly_eps
from src.utils.i18n import SECTOR_KO


@st.cache_data(ttl=3600, show_spinner=False)
def sector_snapshot(tickers: Tuple[str, ...], event_date: date, end_date: date) -> pd.DataFrame:
    """섹터 ETF별: 발발일 이후 수익률, 현재 PER/EPS, 현재가."""
    if not tickers:
        return pd.DataFrame()

    df = get_prices(tickers, start=event_date, end=end_date)
    cls = closes(df)

    rows = []
    for ticker in tickers:
        row = {
            "티커": ticker,
            "섹터": SECTOR_KO.get(ticker, ticker),
            "수익률(%)": np.nan,
            "현재 PER": np.nan,
            "현재 EPS": np.nan,
            "현재가": np.nan,
        }
        if ticker in cls.columns:
            s = cls[ticker].dropna()
            if not s.empty:
                base = s.iloc[0]
                last = s.iloc[-1]
                row["현재가"] = float(last)
                if base and base == base:
                    row["수익률(%)"] = float((last / base - 1.0) * 100.0)
        info = get_info(ticker)
        per = info.get("trailingPE")
        eps = info.get("trailingEps")
        if per is not None and per == per:
            row["현재 PER"] = float(per)
        if eps is not None and eps == eps:
            row["현재 EPS"] = float(eps)
        rows.append(row)

    return pd.DataFrame(rows)[["섹터", "티커", "수익률(%)", "현재 PER", "현재 EPS", "현재가"]]


@st.cache_data(ttl=86400, show_spinner=False)
def build_ttm_eps_series(ticker: str) -> pd.Series:
    """분기 EPS 4분기 롤링합 — 개별 종목용. ETF는 빈 시리즈."""
    eps_q = get_quarterly_eps(ticker)
    if eps_q is None or eps_q.empty or len(eps_q) < 4:
        return pd.Series(dtype=float)
    ttm = eps_q.rolling(window=4).sum().dropna()
    return ttm


def build_per_series(ticker: str, start: date, end: date) -> pd.Series:
    """price ÷ TTM EPS 일별 시계열 — 개별 종목용."""
    ttm = build_ttm_eps_series(ticker)
    if ttm.empty:
        return pd.Series(dtype=float)
    px_df = get_prices((ticker,), start=start, end=end)
    cls = closes(px_df)
    if ticker not in cls.columns:
        return pd.Series(dtype=float)
    px = cls[ticker].dropna()
    ttm_daily = ttm.reindex(px.index, method="ffill")
    per = (px / ttm_daily).dropna()
    return per
