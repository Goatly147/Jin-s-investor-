"""분쟁 타임라인 페이지 — GDELT 자동 수집 뉴스 시계열."""

from collections import defaultdict
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import render_sidebar
from src.data.gdelt import daily_volume, escalation_days, fetch_articles
from src.utils.i18n import t
from src.viz.charts import COLOR_PRIMARY, COLOR_SECONDARY

st.set_page_config(page_title="분쟁 타임라인 | Jin's Investor", layout="wide")


def _volume_chart(vol: pd.Series, escalations: list) -> go.Figure:
    fig = go.Figure(
        go.Bar(x=vol.index, y=vol.values, name="일별 기사 수", marker_color=COLOR_SECONDARY)
    )
    if not vol.empty:
        mean = float(vol.mean())
        fig.add_hline(y=mean, line=dict(color="#A8A8A8", dash="dot"),
                      annotation_text=f"평균 {mean:.0f}", annotation_position="top left")
    for d in escalations:
        fig.add_vline(x=pd.Timestamp(d),
                      line=dict(color=COLOR_PRIMARY, width=1.5, dash="dot"),
                      opacity=0.7)
    fig.update_layout(
        title="GDELT 일별 보도량 (점선: 에스컬레이션 일자, +2σ 이상)",
        height=320, margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
    )
    return fig


def main():
    cfg = render_sidebar()
    st.title("미-이란 분쟁 타임라인")
    st.caption("GDELT 2.0 DOC API에서 영문/한국어 뉴스를 자동 수집합니다. (15분 단위 갱신, API 키 불필요)")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        include_kor = st.checkbox("한국어 기사 포함", value=True)
    with col2:
        z_threshold = st.slider("에스컬레이션 z-score 임계값", 1.0, 4.0, 2.0, 0.1)
    with col3:
        max_per_day = st.number_input("하루당 최대 노출 기사", 1, 20, 5)

    with st.spinner(t("loading")):
        df = fetch_articles(cfg.event_date, cfg.end_date, include_korean=include_kor)

    if df.empty:
        st.warning("기사를 가져오지 못했습니다. 기간을 늘리거나 한국어 옵션을 끄고 다시 시도하세요.")
        return

    vol = daily_volume(df)
    escs = escalation_days(vol, z_threshold=z_threshold)
    st.session_state["gdelt_escalations"] = escs  # 다른 페이지가 사용

    c1, c2, c3 = st.columns(3)
    c1.metric("총 기사 수", f"{len(df):,}")
    c2.metric("커버리지 일수", f"{vol.shape[0]}일")
    c3.metric("에스컬레이션 일자", f"{len(escs)}일")

    st.plotly_chart(_volume_chart(vol, escs), use_container_width=True)

    st.subheader("일자별 주요 기사")
    by_date = defaultdict(list)
    for _, r in df.sort_values("datetime", ascending=False).iterrows():
        d = r["date"]
        if d is None:
            continue
        if len(by_date[d]) < int(max_per_day):
            by_date[d].append(r)

    sorted_dates = sorted(by_date.keys(), reverse=True)
    for d in sorted_dates:
        is_esc = d in escs
        header = f"### {d.isoformat()}" + ("  ⚡ 에스컬레이션" if is_esc else "")
        st.markdown(header)
        for r in by_date[d]:
            title = r.get("title") or "(제목 없음)"
            url = r.get("url")
            domain = r.get("domain") or "-"
            lang = r.get("language") or "-"
            country = r.get("sourcecountry") or "-"
            if url:
                st.markdown(f"- [{title}]({url})  \n  *{domain} · {lang} · {country}*")
            else:
                st.markdown(f"- {title}  \n  *{domain} · {lang} · {country}*")

    st.caption(t("data_source"))


main()
