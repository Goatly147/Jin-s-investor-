"""투자 진입 지표 페이지 — 공포탐욕, CAPE, VIX 백분위, MA200 거리, 수익률 곡선, 방산."""

from datetime import timedelta

import pandas as pd
import streamlit as st

from src.config import ENTRY_AUX_TICKERS, INDEX_TICKERS, MACRO_TICKERS, render_sidebar
from src.data.macro import get_fred_series, get_shiller_cape
from src.data.market import closes, get_prices, returns_since
from src.indicators.fear_greed import compute_fear_greed, label_for
from src.indicators.valuation import (
    cape_zscore,
    latest,
    ma200_distance,
    vix_percentile,
    yield_curve_spread,
)
from src.utils.i18n import t
from src.viz.charts import gauge, returns_lines

st.set_page_config(page_title="진입 지표 | Jin's Investor", layout="wide")


def main():
    cfg = render_sidebar()
    st.title("투자 진입 지표")
    st.caption("심리·밸류에이션·매크로를 결합해 진입 매력도를 점검합니다.")

    tickers = (
        INDEX_TICKERS["VIX"], INDEX_TICKERS["SPY"], INDEX_TICKERS["S&P500"],
        ENTRY_AUX_TICKERS["HYG"], ENTRY_AUX_TICKERS["IEF"],
        ENTRY_AUX_TICKERS["ITA"], ENTRY_AUX_TICKERS["PPA"],
        MACRO_TICKERS["US10Y"],
    )
    df = get_prices(tickers, cfg.lookback_start, cfg.end_date)
    if df.empty:
        st.error(t("no_data"))
        return
    cls = closes(df)

    vix = cls.get(INDEX_TICKERS["VIX"])
    spy = cls.get(INDEX_TICKERS["SPY"])
    sp = cls.get(INDEX_TICKERS["S&P500"])
    hyg = cls.get(ENTRY_AUX_TICKERS["HYG"])
    ief = cls.get(ENTRY_AUX_TICKERS["IEF"])

    # 1) Fear & Greed
    st.subheader("공포탐욕 지수 (4-factor 프록시)")
    fg = compute_fear_greed(vix, spy, hyg, ief)
    overall = fg.get("종합", float("nan"))

    g1, g2, g3 = st.columns([1, 1, 2])
    with g1:
        st.plotly_chart(gauge(overall if not pd.isna(overall) else 50, "종합 (0=공포, 100=탐욕)"),
                        use_container_width=True)
    with g2:
        st.metric("해석", label_for(overall))
    with g3:
        bd = pd.DataFrame(
            [{"요인": k, "점수(0-100)": v} for k, v in fg.items() if k != "종합"]
        )
        st.dataframe(bd.style.format({"점수(0-100)": "{:.1f}"}, na_rep="—"),
                     hide_index=True, use_container_width=True)

    st.divider()

    # 2) Valuation
    st.subheader("밸류에이션·추세 지표")
    cape = get_shiller_cape()
    cape_z = cape_zscore(cape) if cape is not None else float("nan")
    cape_now = latest(cape) if cape is not None else float("nan")
    vix_pct = vix_percentile(vix) if vix is not None else pd.Series(dtype=float)
    vix_pct_now = latest(vix_pct)
    ma_dist = ma200_distance(sp) if sp is not None else pd.Series(dtype=float)
    ma_dist_now = latest(ma_dist) * 100.0 if not ma_dist.empty else float("nan")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shiller CAPE", f"{cape_now:.1f}" if not pd.isna(cape_now) else "—",
              f"z {cape_z:+.2f}" if not pd.isna(cape_z) else "")
    c2.metric("VIX 1년 백분위",
              f"{vix_pct_now:.0f}%" if not pd.isna(vix_pct_now) else "—")
    c3.metric("S&P 200일 이평 거리",
              f"{ma_dist_now:+.2f}%" if not pd.isna(ma_dist_now) else "—")
    us10y_last = latest(cls.get(MACRO_TICKERS["US10Y"]))
    c4.metric("미 10년물 (%)",
              f"{us10y_last:.2f}" if not pd.isna(us10y_last) else "—")

    if cape is not None and not cape.empty:
        st.line_chart(cape.rename("Shiller CAPE").to_frame(), height=260)
        st.caption("Shiller CAPE — 인플레이션 조정 10년 평균 EPS 기반 PER. 역사적 평균 ≈17, >30은 고평가권.")

    if not vix_pct.empty:
        st.line_chart(vix_pct.rename("VIX 1년 백분위").to_frame(), height=240)

    st.divider()

    # 3) Yield curve
    st.subheader("미 국채 수익률 곡선")
    us10y = cls.get(MACRO_TICKERS["US10Y"])
    dgs2 = get_fred_series("DGS2")
    if us10y is not None and not us10y.empty and not dgs2.empty:
        us10y = us10y.dropna()
        spread = yield_curve_spread(us10y, dgs2).loc[str(cfg.lookback_start):]
        st.line_chart(spread.rename("10Y-2Y (%p)").to_frame(), height=260)
        latest_spread = latest(spread)
        if not pd.isna(latest_spread):
            warn = "역전 (침체 신호)" if latest_spread < 0 else "정상"
            st.metric("현재 스프레드", f"{latest_spread:+.2f}%p", warn)
    else:
        st.caption("FRED DGS2를 가져올 수 없어 수익률 곡선을 표시하지 못했습니다.")

    st.divider()

    # 4) Defense ETFs
    st.subheader("방산 ETF — 발발일 이후 수익률")
    defense = cls[[c for c in (ENTRY_AUX_TICKERS["ITA"], ENTRY_AUX_TICKERS["PPA"]) if c in cls.columns]]
    defense_window = defense.loc[str(cfg.event_date - timedelta(days=2)):]
    rets = returns_since(defense_window, cfg.event_date)
    if not rets.empty:
        rename_map = {ENTRY_AUX_TICKERS["ITA"]: "ITA (방산)", ENTRY_AUX_TICKERS["PPA"]: "PPA (항공·방산)"}
        rets = rets.rename(columns={k: v for k, v in rename_map.items() if k in rets.columns})
        escalations = st.session_state.get("gdelt_escalations", [])
        st.plotly_chart(
            returns_lines(rets, anchor=cfg.event_date, escalations=escalations,
                          title="방산 ETF 누적 수익률"),
            use_container_width=True,
        )

    with st.expander("계산 방식"):
        st.markdown(
            """
- **공포탐욕 (4-factor 프록시)**: VIX 역백분위 / S&P 125일 모멘텀 / 52주 고저 위치 / HYG-IEF 20일 스프레드. CNN 공식 지수의 7요인 중 무료로 산출 가능한 4개를 평균.
- **Shiller CAPE z-score**: 최근 30년 평균/표준편차 대비 현재 위치.
- **VIX 백분위**: 252일 롤링 윈도우에서의 현재 값 위치.
- **200일 이평 거리**: `(Close − MA200) / MA200`. 양수면 강세 추세.
- **수익률 곡선**: 미 10년물(`^TNX`) − FRED `DGS2`(2년).
            """
        )


main()
