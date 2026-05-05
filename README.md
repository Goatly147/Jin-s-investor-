# Jin's Investor — 미-이란 분쟁 & 시장 대시보드

미국-이란 분쟁 관련 뉴스 시계열과 시장 지표(S&P 500, 11개 SPDR 섹터, VIX, 매크로, 진입 지표)를 결합한 Streamlit 대시보드.

## 핵심 설계 원칙

> 본 대시보드는 특정 분쟁의 발발 시점을 단정하지 않습니다.

- **발발일은 사용자가 지정** — 사이드바에서 날짜를 직접 선택하거나 프리셋(최근 30/90일, YTD, 1년)을 사용
- **뉴스는 GDELT 2.0 DOC API에서 자동 수집** — 무료, API 키 불필요, 15분 단위 갱신
- **에스컬레이션 일자는 통계적으로 검출** — 일별 보도량 z-score > 2σ 일자를 자동 표시
- **금융 데이터는 yfinance + FRED + Shiller**로 모두 무료

## 페이지 구성

| 페이지 | 내용 |
|---|---|
| 홈 | KPI 카드(S&P, VIX, WTI, Gold, ITA), S&P+VIX 차트 |
| 분쟁 타임라인 | GDELT 영문/한국어 뉴스 시계열, 일별 보도량, 에스컬레이션 일자 |
| 시장 지수 | S&P 500 + VIX 듀얼축, 발발일 이후 누적 수익률 |
| 섹터 ETF | 11개 SPDR(XLK~XLC) 수익률·현재 PER/EPS 표·바·시계열 |
| 매크로 지표 | WTI/Brent/DXY/Gold 2×2, 10Y-2Y 수익률 곡선 |
| 투자 진입 지표 | 공포탐욕 4-factor, Shiller CAPE, VIX 백분위, 200일 MA 거리, 수익률 곡선, 방산 ETF |

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

기본 포트: http://localhost:8501

## 데이터 소스

| 종류 | 소스 | 키 필요? |
|---|---|---|
| 주가/ETF/지수 | yfinance (Yahoo Finance) | ✕ |
| 뉴스 타임라인 | GDELT 2.0 DOC API | ✕ |
| 미 국채 수익률 (DGS2) | FRED CSV | ✕ |
| Shiller CAPE | Yale Shiller xls | ✕ |

## 한계 및 주의사항

- **섹터 ETF의 PER/EPS는 시계열이 아닌 현재 스냅샷**입니다 (yfinance가 ETF 분기 EPS를 제공하지 않음). 시계열은 발발일 기준 종가 수익률로 표시.
- **공포탐욕지수는 4-factor 프록시**입니다 (CNN 공식 7요인 중 무료로 산출 가능한 것만). 추세 비교용이지 절대 비교용이 아닙니다.
- yfinance `Ticker.info`는 종목에 따라 일부 필드가 누락될 수 있습니다 — 표에서는 "—"로 표시.
- 본 대시보드는 정보 제공용이며 투자 조언이 아닙니다.

## 디렉토리 구조

```
Jin-s-investor-/
├── app.py                      # 홈
├── pages/
│   ├── 1_타임라인.py
│   ├── 2_시장지수.py
│   ├── 3_섹터ETF.py
│   ├── 4_매크로.py
│   └── 5_진입지표.py
├── src/
│   ├── config.py               # AppConfig + 사이드바 + 티커 상수
│   ├── data/
│   │   ├── market.py           # yfinance 래퍼
│   │   ├── gdelt.py            # GDELT 클라이언트
│   │   ├── fundamentals.py     # 섹터 스냅샷
│   │   └── macro.py            # FRED + Shiller
│   ├── indicators/
│   │   ├── fear_greed.py
│   │   └── valuation.py
│   ├── viz/
│   │   ├── charts.py
│   │   └── tables.py
│   └── utils/
│       ├── cache.py
│       └── i18n.py
├── assets/presets.json
├── .streamlit/config.toml
├── requirements.txt
└── README.md
```

## 캐시 전략

- `st.cache_data` TTL: 시장(15분), GDELT(30분), 펀더멘털·CAPE(24시간)
- 디스크 영속화: `joblib.Memory(.cache/)` — 앱 재시작 시 즉시 가용
- 강제 새로고침: 사이드바 "데이터 새로고침" 버튼
