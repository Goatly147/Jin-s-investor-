"""밸류에이션·추세 지표 — CAPE z-score, MA200 거리, VIX 백분위."""

import numpy as np
import pandas as pd


def cape_zscore(cape: pd.Series, window_years: int = 30) -> float:
    """최근 window_years 평균/표준편차 기준 현재 CAPE의 z-score."""
    if cape is None or cape.empty:
        return float("nan")
    window = cape.last(f"{window_years * 365}D")
    if window.empty or len(window) < 12:
        return float("nan")
    mean = window.mean()
    std = window.std(ddof=0)
    if std == 0 or pd.isna(std):
        return float("nan")
    return float((cape.iloc[-1] - mean) / std)


def ma200_distance(close: pd.Series) -> pd.Series:
    """(Close - MA200) / MA200 — 양수면 추세 강함."""
    if close is None or close.empty:
        return pd.Series(dtype=float)
    ma = close.rolling(window=200, min_periods=50).mean()
    return ((close - ma) / ma).dropna()


def vix_percentile(vix: pd.Series, window: int = 252) -> pd.Series:
    """롤링 252일 윈도우에서 현재 VIX의 백분위(0-100)."""
    if vix is None or vix.empty:
        return pd.Series(dtype=float)
    return vix.rolling(window=window, min_periods=60).apply(
        lambda x: (x.rank(pct=True).iloc[-1]) * 100.0, raw=False
    ).dropna()


def yield_curve_spread(us10y: pd.Series, us2y: pd.Series) -> pd.Series:
    df = pd.DataFrame({"y10": us10y, "y2": us2y}).dropna()
    return (df["y10"] - df["y2"]).rename("10Y-2Y")


def latest(series: pd.Series, default: float = float("nan")) -> float:
    if series is None or series.empty:
        return default
    return float(series.dropna().iloc[-1])
