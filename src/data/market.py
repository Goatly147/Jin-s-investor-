"""yfinance 래퍼 — 가격 시계열, info 스칼라, 분기 EPS."""

from datetime import date
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd
import streamlit as st
import yfinance as yf


def _flatten_columns(df: pd.DataFrame, tickers: Tuple[str, ...]) -> pd.DataFrame:
    """yf.download의 MultiIndex 컬럼을 flat 형태로 변환."""
    if isinstance(df.columns, pd.MultiIndex):
        out = pd.DataFrame(index=df.index)
        for field, ticker in df.columns:
            out[f"{field}_{ticker}"] = df[(field, ticker)]
        return out
    if len(tickers) == 1:
        df = df.copy()
        df.columns = [f"{c}_{tickers[0]}" for c in df.columns]
    return df


@st.cache_data(ttl=900, show_spinner=False)
def get_prices(
    tickers: Tuple[str, ...],
    start: date,
    end: date,
) -> pd.DataFrame:
    """여러 티커의 OHLCV를 flat 컬럼 DataFrame으로 반환."""
    if not tickers:
        return pd.DataFrame()
    df = yf.download(
        list(tickers),
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df = _flatten_columns(df, tickers)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.sort_index()


def closes(df: pd.DataFrame) -> pd.DataFrame:
    """flat 컬럼 가격 프레임에서 Close_* 만 추출 (티커명 컬럼)."""
    cols = [c for c in df.columns if c.startswith("Close_")]
    out = df[cols].copy()
    out.columns = [c.replace("Close_", "") for c in cols]
    return out.dropna(how="all")


def returns_since(close_df: pd.DataFrame, anchor: date) -> pd.DataFrame:
    """앵커 날짜 기준 누적 수익률(%)."""
    if close_df.empty:
        return close_df
    anchor_ts = pd.Timestamp(anchor)
    idx = close_df.index
    pos = idx.searchsorted(anchor_ts)
    if pos >= len(idx):
        return pd.DataFrame()
    base = close_df.iloc[pos]
    return (close_df / base - 1.0) * 100.0


@st.cache_data(ttl=86400, show_spinner=False)
def get_info(ticker: str) -> Dict:
    """yf.Ticker.info — trailingPE/EPS 등 스칼라. 실패 시 빈 dict."""
    try:
        t = yf.Ticker(ticker)
        info = dict(t.info or {})
        if "trailingPE" not in info or info.get("trailingPE") is None:
            try:
                fast = t.fast_info
                info.setdefault("regularMarketPrice", getattr(fast, "last_price", None))
            except Exception:
                pass
        return info
    except Exception:
        return {}


@st.cache_data(ttl=86400, show_spinner=False)
def get_quarterly_eps(ticker: str) -> Optional[pd.Series]:
    """분기 Diluted EPS — 개별 종목용. ETF는 빈 결과."""
    try:
        t = yf.Ticker(ticker)
        qis = t.quarterly_income_stmt
        if qis is None or qis.empty:
            return None
        if "Diluted EPS" in qis.index:
            s = qis.loc["Diluted EPS"].dropna().sort_index()
            s.index = pd.to_datetime(s.index)
            return s.astype(float)
        if "Net Income" in qis.index and "Diluted Average Shares" in qis.index:
            ni = qis.loc["Net Income"].astype(float)
            sh = qis.loc["Diluted Average Shares"].astype(float)
            s = (ni / sh).dropna().sort_index()
            s.index = pd.to_datetime(s.index)
            return s
        return None
    except Exception:
        return None


def latest_close(close_df: pd.DataFrame, ticker: str) -> Optional[float]:
    if ticker not in close_df.columns or close_df[ticker].dropna().empty:
        return None
    return float(close_df[ticker].dropna().iloc[-1])


def fetch_universe(start: date, end: date, extras: Iterable[str] = ()) -> pd.DataFrame:
    """대시보드에서 자주 쓰는 모든 티커를 한 번에 받기."""
    from src.config import (
        ENTRY_AUX_TICKERS,
        INDEX_TICKERS,
        MACRO_TICKERS,
        SECTOR_TICKERS,
    )

    tickers = (
        list(INDEX_TICKERS.values())
        + list(SECTOR_TICKERS)
        + list(MACRO_TICKERS.values())
        + list(ENTRY_AUX_TICKERS.values())
        + list(extras)
    )
    seen, deduped = set(), []
    for t in tickers:
        if t not in seen:
            deduped.append(t)
            seen.add(t)
    return get_prices(tuple(deduped), start, end)
