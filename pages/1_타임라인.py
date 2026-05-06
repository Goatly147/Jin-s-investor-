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
        ts = pd.Timestamp(d)
        fig.add_shape(type="line", xref="x", yref="paper",
                      x0=ts, x1=ts, y0=0, y1=1,
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
        df, diag = fetch_articles(cfg.event_date, cfg.end_date, include_korean=include_kor)

    if df.empty:
        st.warning("기사를 가져오지 못했습니다. 아래 진단 정보로 원인을 확인하세요.")
        with st.expander("진단 정보 (호출별 상태)", expanded=True):
            errors = [d for d in diag if d.get("error")]
            if errors:
                st.error(f"에러 {len(errors)}건 / 총 호출 {len(diag)}건")
                err_df = pd.DataFrame(errors)
                st.dataframe(err_df, use_container_width=True, hide_index=True)
            else:
                st.info("에러는 없지만 모든 윈도우에서 0건 반환됐습니다 — GDELT 인덱스에 해당 기간·쿼리에 매칭되는 기사가 없거나, 쿼리가 너무 좁습니다.")
                st.dataframe(pd.DataFrame(diag), use_container_width=True, hide_index=True)
            st.caption(
                "흔한 원인: (1) GDELT 레이트 제한 — 잠시 후 '데이터 새로고침' 클릭. "
                "(2) 쿼리가 GDELT 인덱스 기준으로 너무 좁음 — 발발일 기간을 넓히세요. "
                "(3) Streamlit Cloud 출구 IP가 GDELT에 의해 일시적으로 차단."
            )
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
