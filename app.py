"""Jin's Investor — 홈 페이지."""

import pandas as pd
import streamlit as st

from src.config import (
    ENTRY_AUX_TICKERS,
    INDEX_TICKERS,
    MACRO_TICKERS,
    SECTOR_TICKERS,
    render_sidebar,
)
from src.data.market import closes, fetch_universe, latest_close, returns_since
from src.utils.i18n import t
from src.viz.charts import price_with_events

st.set_page_config(
    page_title="Jin's Investor",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _pct(close_df, ticker, anchor):
    if ticker not in close_df.columns:
        return None
    s = close_df[ticker].dropna()
    if s.empty:
        return None
    pos = s.index.searchsorted(pd.Timestamp(anchor))
    if pos >= len(s):
        return None
    base = s.iloc[pos]
    last = s.iloc[-1]
    if base == 0 or base != base:  # NaN check
        return None
    return (last / base - 1.0) * 100.0


def main():
    cfg = render_sidebar()

    st.title(t("app_title"))
    st.caption(t("app_subtitle"))

    universe = fetch_universe(cfg.lookback_start, cfg.end_date)
    if universe.empty:
        st.error(t("no_data"))
        return

    cls = closes(universe)

    sp = _pct(cls, INDEX_TICKERS["S&P500"], cfg.event_date)
    vix_now = latest_close(cls, INDEX_TICKERS["VIX"])
    oil = _pct(cls, MACRO_TICKERS["WTI"], cfg.event_date)
    gold = _pct(cls, MACRO_TICKERS["Gold"], cfg.event_date)
    ita = _pct(cls, ENTRY_AUX_TICKERS["ITA"], cfg.event_date)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t("kpi_sp500"), f"{sp:+.2f}%" if sp is not None else "—")
    c2.metric(t("kpi_vix"), f"{vix_now:.2f}" if vix_now is not None else "—")
    c3.metric(t("kpi_oil"), f"{oil:+.2f}%" if oil is not None else "—")
    c4.metric(t("kpi_gold"), f"{gold:+.2f}%" if gold is not None else "—")
    c5.metric(t("kpi_defense"), f"{ita:+.2f}%" if ita is not None else "—")

    st.divider()

    sp_series = cls.get(INDEX_TICKERS["S&P500"])
    vix_series = cls.get(INDEX_TICKERS["VIX"])
    if sp_series is not None and not sp_series.dropna().empty:
        sp_series = sp_series.dropna().loc[str(cfg.buffer_start):]
        vix_clip = vix_series.dropna().loc[str(cfg.buffer_start):] if vix_series is not None else None
        fig = price_with_events(sp_series, vix_clip, anchor=cfg.event_date,
                                title="S&P 500 + VIX (발발일 기준)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("페이지 안내")
    st.markdown(
        """
- **분쟁 타임라인**: GDELT 2.0에서 자동 수집한 미-이란 관련 영문/한국어 뉴스 시계열. 일별 보도량 z-score >2σ 일자를 *에스컬레이션 일자*로 표시.
- **시장 지수**: S&P 500과 VIX를 발발일·에스컬레이션 일자 마커와 함께 비교.
- **섹터 ETF**: 11개 SPDR 섹터(XLK~XLC)의 발발일 이후 수익률·현재 PER/EPS 스냅샷.
- **매크로 지표**: WTI/Brent 원유, 달러 인덱스(DXY), 미 10년물 금리, 금.
- **투자 진입 지표**: 공포탐욕 4-factor 프록시, Shiller CAPE, VIX 백분위, 200일 이평선 거리, 수익률 곡선, 방산 ETF.
        """
    )

    st.caption(t("disclaimer"))


if __name__ == "__main__":
    main()
