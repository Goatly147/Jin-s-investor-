"""시장 지수 페이지 — S&P 500 + VIX 듀얼축 + 이벤트 오버레이."""

from datetime import timedelta

import streamlit as st

from src.config import INDEX_TICKERS, render_sidebar
from src.data.market import closes, get_prices, returns_since
from src.utils.i18n import t
from src.viz.charts import price_with_events, returns_lines

st.set_page_config(page_title="시장 지수 | Jin's Investor", layout="wide")


def main():
    cfg = render_sidebar()
    st.title("시장 지수")
    st.caption("S&P 500과 VIX의 발발일 전후 흐름을 비교합니다.")

    tickers = (INDEX_TICKERS["S&P500"], INDEX_TICKERS["VIX"], INDEX_TICKERS["SPY"])
    df = get_prices(tickers, cfg.lookback_start, cfg.end_date)
    if df.empty:
        st.error(t("no_data"))
        return
    cls = closes(df)

    sp = cls.get(INDEX_TICKERS["S&P500"])
    vix = cls.get(INDEX_TICKERS["VIX"])
    spy = cls.get(INDEX_TICKERS["SPY"])

    escalations = st.session_state.get("gdelt_escalations", [])

    if sp is not None and not sp.dropna().empty:
        clip_start = str(cfg.buffer_start)
        sp_clip = sp.dropna().loc[clip_start:]
        vix_clip = vix.dropna().loc[clip_start:] if vix is not None else None
        fig = price_with_events(
            sp_clip, vix_clip,
            anchor=cfg.event_date,
            escalations=escalations,
            title="S&P 500 (좌축) + VIX (우축)",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader(t("return_since_event"))
    cls_window = cls.loc[str(cfg.event_date - timedelta(days=2)):]
    rets = returns_since(cls_window[[c for c in [INDEX_TICKERS["S&P500"], INDEX_TICKERS["SPY"]] if c in cls_window.columns]], cfg.event_date)
    if not rets.empty:
        rets = rets.rename(columns={INDEX_TICKERS["S&P500"]: "S&P 500", INDEX_TICKERS["SPY"]: "SPY"})
        fig2 = returns_lines(rets, anchor=cfg.event_date, escalations=escalations,
                             title="발발일 이후 누적 수익률")
        st.plotly_chart(fig2, use_container_width=True)

    if escalations:
        st.info(f"GDELT 에스컬레이션 일자 {len(escalations)}건이 점선으로 표시됩니다. (자세히는 '분쟁 타임라인' 페이지)")
    else:
        st.caption("'분쟁 타임라인' 페이지를 먼저 열어두면 에스컬레이션 일자가 차트에 표시됩니다.")


main()
