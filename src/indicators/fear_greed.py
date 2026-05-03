"""4-factor 공포탐욕지수 프록시.

요인 (각 0–100, 평균):
  1. VIX inverse — 현 VIX의 1년 백분위를 100에서 뺀 값 (낮은 변동성=탐욕)
  2. S&P 125일 모멘텀 — 125일 이평 대비 SPY 등락의 1년 백분위
  3. 52주 고/저 강도 — SPY가 52주 고점/저점 사이에서 차지하는 위치
  4. HYG/IEF 스프레드 — 20일 수익률 차의 1년 백분위 (정크채 선호=탐욕)
"""

from typing import Dict, Optional

import numpy as np
import pandas as pd


def _percentile_last(s: pd.Series, lookback: int = 252) -> float:
    s = s.dropna().iloc[-lookback:]
    if len(s) < 30:
        return float("nan")
    return float(s.rank(pct=True).iloc[-1] * 100.0)


def _vix_score(vix: pd.Series) -> Optional[float]:
    p = _percentile_last(vix, lookback=252)
    return None if pd.isna(p) else 100.0 - p


def _momentum_score(spy: pd.Series) -> Optional[float]:
    if spy is None or spy.empty:
        return None
    ma = spy.rolling(window=125, min_periods=60).mean()
    momentum = (spy / ma - 1.0).dropna()
    p = _percentile_last(momentum, lookback=252)
    return None if pd.isna(p) else p


def _strength_score(spy: pd.Series) -> Optional[float]:
    if spy is None or spy.empty:
        return None
    s = spy.dropna().iloc[-252:]
    if len(s) < 60:
        return None
    hi, lo = s.max(), s.min()
    if hi == lo:
        return 50.0
    pos = (s.iloc[-1] - lo) / (hi - lo)
    return float(np.clip(pos * 100.0, 0, 100))


def _junk_score(hyg: pd.Series, ief: pd.Series) -> Optional[float]:
    if hyg is None or ief is None or hyg.empty or ief.empty:
        return None
    df = pd.DataFrame({"hyg": hyg, "ief": ief}).dropna()
    if len(df) < 60:
        return None
    spread = df["hyg"].pct_change(20) - df["ief"].pct_change(20)
    p = _percentile_last(spread, lookback=252)
    return None if pd.isna(p) else p


def compute_fear_greed(
    vix: pd.Series,
    spy: pd.Series,
    hyg: Optional[pd.Series] = None,
    ief: Optional[pd.Series] = None,
) -> Dict[str, float]:
    parts: Dict[str, Optional[float]] = {
        "VIX 역백분위": _vix_score(vix),
        "S&P 125일 모멘텀": _momentum_score(spy),
        "52주 고/저 위치": _strength_score(spy),
        "HYG/IEF 스프레드": _junk_score(hyg, ief),
    }
    valid = {k: v for k, v in parts.items() if v is not None and not pd.isna(v)}
    score = float(np.mean(list(valid.values()))) if valid else float("nan")
    out = {k: float(v) if v is not None else float("nan") for k, v in parts.items()}
    out["종합"] = score
    return out


def label_for(score: float) -> str:
    if pd.isna(score):
        return "—"
    if score < 25:
        return "극단적 공포"
    if score < 45:
        return "공포"
    if score < 55:
        return "중립"
    if score < 75:
        return "탐욕"
    return "극단적 탐욕"
