"""한국어 라벨 사전 — UI 텍스트 일원화."""

LABELS = {
    "app_title": "Jin's Investor",
    "app_subtitle": "미-이란 분쟁 & 시장 대시보드",
    "sidebar_header": "분석 설정",
    "event_date": "분쟁 발발일",
    "event_date_help": "이 날짜를 기준으로 누적 수익률·차트 마커를 계산합니다.",
    "preset_label": "기간 프리셋",
    "preset_30d": "최근 30일",
    "preset_90d": "최근 90일",
    "preset_ytd": "올해 누적 (YTD)",
    "preset_1y": "최근 1년",
    "preset_custom": "사용자 지정",
    "refresh": "데이터 새로고침",
    "page_home": "홈",
    "page_timeline": "분쟁 타임라인",
    "page_index": "시장 지수",
    "page_sector": "섹터 ETF",
    "page_macro": "매크로 지표",
    "page_entry": "투자 진입 지표",
    "kpi_sp500": "S&P 500 (발발일 이후)",
    "kpi_vix": "VIX (현재)",
    "kpi_oil": "WTI 원유 (발발일 이후)",
    "kpi_gold": "금 (발발일 이후)",
    "kpi_defense": "방산 ETF (ITA, 발발일 이후)",
    "return_since_event": "발발일 이후 수익률",
    "current_per": "현재 PER",
    "current_eps": "현재 EPS",
    "sector_table_title": "섹터 ETF 스냅샷",
    "loading": "데이터 불러오는 중...",
    "no_data": "데이터를 가져올 수 없습니다.",
    "data_source": "데이터: yfinance / GDELT 2.0 / FRED / Shiller",
    "disclaimer": "본 대시보드는 정보 제공용이며 투자 조언이 아닙니다.",
    "fact_caveat": "본 대시보드는 특정 분쟁의 발발 시점을 단정하지 않습니다. 사용자가 지정한 날짜를 기준으로 분석되며, 뉴스는 GDELT 실시간 데이터에 의해 자동 수집됩니다.",
}

SECTOR_KO = {
    "XLK": "기술",
    "XLV": "헬스케어",
    "XLF": "금융",
    "XLY": "임의소비재",
    "XLI": "산업재",
    "XLP": "필수소비재",
    "XLE": "에너지",
    "XLU": "유틸리티",
    "XLB": "소재",
    "XLRE": "부동산",
    "XLC": "커뮤니케이션",
}


def t(key: str) -> str:
    """라벨 lookup. 키 누락 시 키 자체를 반환."""
    return LABELS.get(key, key)
