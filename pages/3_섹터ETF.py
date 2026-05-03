"""섹터 ETF 페이지 — 11개 SPDR 섹터 스냅샷 + 수익률 시계열."""

from datetime import timedelta

import streamlit as st

from src.config import SECTOR_TICKERS, render_sidebar
from src.data.fundamentals import sector_snapshot
from src.data.market import closes, get_prices, returns_since
from src.utils.i18n import SECTOR_KO, t
from src.viz.charts import returns_lines, sector_bar
from src.viz.tables import style_sector_table

st.set_page_config(page_title="섹터 ETF | Jin's Investor", layout="wide")


def main():
    cfg = render_sidebar()
    st.title("섹터 ETF 스냅샷")
    st.caption("S&P 500을 11개 SPDR 섹터 ETF로 나눠 발발일 이후 성과·밸류에이션을 비교합니다.")

    snap = sector_snapshot(SECTOR_TICKERS, cfg.event_date, cfg.end_date)
    if snap.empty:
        st.error(t("no_data"))
        return

    st.subheader(t("sector_table_title"))
    st.dataframe(style_sector_table(snap), use_container_width=True, hide_index=True)

    fig = sector_bar(snap.dropna(subset=["수익률(%)"]))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("발발일 이후 누적 수익률")
    df = get_prices(SECTOR_TICKERS, cfg.event_date - timedelta(days=2), cfg.end_date)
    cls = closes(df)
    rets = returns_since(cls, cfg.event_date)
    if not rets.empty:
        rets = rets.rename(columns={k: f"{SECTOR_KO.get(k, k)} ({k})" for k in rets.columns})
        escalations = st.session_state.get("gdelt_escalations", [])
        fig2 = returns_lines(rets, anchor=cfg.event_date, escalations=escalations,
                             title="11개 섹터 ETF 누적 수익률")
        st.plotly_chart(fig2, use_container_width=True)

    with st.expander("PER/EPS 데이터 출처 안내"):
        st.markdown(
            """
- 섹터 ETF는 분기 EPS를 별도로 보고하지 않으므로 **현재 PER/EPS는 yfinance `info.trailingPE` / `trailingEps` 스칼라**를 사용합니다.
- 시계열 PER/EPS는 ETF 구성종목 가중치를 곱한 bottom-up 계산이 필요해 본 대시보드 v1에서는 제공하지 않습니다.
- 발발일 이후 **수익률 시계열**은 종가 기반(`Close_t / Close_event - 1`)으로 정확합니다.
            """
        )


main()
