"""대시보드 전역 설정 — AppConfig dataclass, 티커 상수, 프리셋."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Tuple

import streamlit as st

from src.utils.i18n import t

SECTOR_TICKERS: Tuple[str, ...] = (
    "XLK", "XLV", "XLF", "XLY", "XLI",
    "XLP", "XLE", "XLU", "XLB", "XLRE", "XLC",
)

INDEX_TICKERS = {
    "S&P500": "^GSPC",
    "VIX": "^VIX",
    "SPY": "SPY",
}

MACRO_TICKERS = {
    "WTI": "CL=F",
    "Brent": "BZ=F",
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
    "US5Y": "^FVX",
    "US3M": "^IRX",
    "Gold": "GC=F",
}

ENTRY_AUX_TICKERS = {
    "ITA": "ITA",
    "PPA": "PPA",
    "HYG": "HYG",
    "IEF": "IEF",
}


def preset_dates() -> dict:
    today = date.today()
    return {
        t("preset_30d"): today - timedelta(days=30),
        t("preset_90d"): today - timedelta(days=90),
        t("preset_ytd"): date(today.year, 1, 1),
        t("preset_1y"): today - timedelta(days=365),
        t("preset_custom"): None,
    }


@dataclass
class AppConfig:
    event_date: date
    end_date: date = field(default_factory=date.today)

    @property
    def buffer_start(self) -> date:
        """차트 컨텍스트용 버퍼(이벤트 이전 30일)."""
        return self.event_date - timedelta(days=30)

    @property
    def lookback_start(self) -> date:
        """진입 지표·MA200 등을 위해 충분히 긴 룩백."""
        return self.event_date - timedelta(days=400)


def render_sidebar() -> AppConfig:
    """사이드바 위젯 + AppConfig 반환. 모든 페이지에서 호출."""
    st.sidebar.markdown(f"### {t('sidebar_header')}")

    presets = preset_dates()
    preset_choice = st.sidebar.selectbox(
        t("preset_label"),
        options=list(presets.keys()),
        index=1,  # 기본 90일
    )

    today = date.today()
    if presets[preset_choice] is not None:
        default_event = presets[preset_choice]
    else:
        default_event = st.session_state.get("custom_event_date", today - timedelta(days=90))

    event_date = st.sidebar.date_input(
        t("event_date"),
        value=default_event,
        max_value=today,
        min_value=date(2000, 1, 1),
        help=t("event_date_help"),
    )
    st.session_state["custom_event_date"] = event_date

    if st.sidebar.button(t("refresh")):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.caption(t("data_source"))
    st.sidebar.caption(t("fact_caveat"))

    return AppConfig(event_date=event_date, end_date=today)
