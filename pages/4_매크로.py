"""매크로 페이지 — 유가, 달러 인덱스, 미 10년물, 금."""

from datetime import timedelta

import pandas as pd
import streamlit as st

from src.config import MACRO_TICKERS, render_sidebar
from src.data.macro import get_fred_series
from src.data.market import closes, get_prices, returns_since
from src.utils.i18n import t
from src.viz.charts import returns_lines, small_multiples

st.set_page_config(page_title="매크로 | Jin's Investor", layout="wide")


def main():
    cfg = render_sidebar()
    st.title("매크로 지표")
    st.caption("중동 분쟁 시 핵심 거시변수: 유가(WTI/Brent), 달러 인덱스(DXY), 미 10년물 금리, 금.")

    tickers = (
        MACRO_TICKERS["WTI"], MACRO_TICKERS["Brent"], MACRO_TICKERS["DXY"],
        MACRO_TICKERS["US10Y"], MACRO_TICKERS["Gold"],
    )
    df = get_prices(tickers, cfg.lookback_start, cfg.end_date)
    if df.empty:
        st.error(t("no_data"))
        return
    cls = closes(df)

    series_dict = {
        "WTI ($/배럴)": cls.get(MACRO_TICKERS["WTI"]),
        "Brent ($/배럴)": cls.get(MACRO_TICKERS["Brent"]),
        "DXY (달러 인덱스)": cls.get(MACRO_TICKERS["DXY"]),
        "Gold ($/온스)": cls.get(MACRO_TICKERS["Gold"]),
    }
    series_dict = {k: (v.dropna() if v is not None else None) for k, v in series_dict.items()}
    st.plotly_chart(small_multiples(series_dict, title="주요 매크로 (lookback 400일)"),
                    use_container_width=True)

    st.subheader("발발일 이후 누적 수익률")
    cls_window = cls.loc[str(cfg.event_date - timedelta(days=2)):]
    valid = [c for c in cls_window.columns if c in (
        MACRO_TICKERS["WTI"], MACRO_TICKERS["Brent"], MACRO_TICKERS["DXY"],
        MACRO_TICKERS["Gold"],
    )]
    rets = returns_since(cls_window[valid], cfg.event_date)
    rename_map = {v: k for k, v in MACRO_TICKERS.items() if v in rets.columns}
    rets = rets.rename(columns=rename_map)
    if not rets.empty:
        escalations = st.session_state.get("gdelt_escalations", [])
        st.plotly_chart(
            returns_lines(rets, anchor=cfg.event_date, escalations=escalations,
                          title="매크로 발발일 이후 수익률"),
            use_container_width=True,
        )

    st.subheader("미 국채 수익률 곡선")
    us10y = cls.get(MACRO_TICKERS["US10Y"])
    if us10y is not None:
        us10y = us10y.dropna()
    dgs2 = get_fred_series("DGS2")
    if us10y is not None and not us10y.empty and not dgs2.empty:
        joined = pd.DataFrame({"US10Y": us10y, "US2Y": dgs2}).dropna()
        joined["10Y-2Y"] = joined["US10Y"] - joined["US2Y"]
        joined = joined.loc[str(cfg.lookback_start):]

        c1, c2 = st.columns(2)
        with c1:
            spread = joined[["10Y-2Y"]].rename(columns={"10Y-2Y": "10Y-2Y 스프레드(%p)"})
            st.line_chart(spread, height=320)
            st.caption("음수 = 장단기 금리 역전(역사적 침체 선행 지표).")
        with c2:
            st.line_chart(joined[["US10Y", "US2Y"]].rename(columns={"US10Y": "미 10Y(%)", "US2Y": "미 2Y(%)"}),
                          height=320)
    else:
        st.caption("FRED DGS2를 가져올 수 없어 수익률 곡선을 표시하지 못했습니다.")


main()
