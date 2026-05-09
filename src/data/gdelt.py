"""GDELT 2.0 DOC API 클라이언트 — 미-이란 분쟁 뉴스 자동 수집."""

import hashlib
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st

from src.utils.cache import get_session

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# 분쟁 보도 surface 쿼리 — 영문/한국어 별도 호출 후 병합
QUERY_EN = (
    '(sourcelang:eng) AND ("United States" OR US OR "U.S.") '
    'AND (Iran OR Tehran OR Iranian) '
    'AND (theme:ARMEDCONFLICT OR theme:CRISISLEX_CRISISLEXREC OR theme:KILL '
    'OR theme:WB_840_CONFLICT_AND_FRAGILITY OR theme:TAX_MILITARY_TITLES)'
)

QUERY_KO = (
    '(sourcelang:kor) AND (미국 OR 미군) AND (이란 OR 테헤란) '
    'AND (theme:ARMEDCONFLICT OR theme:CRISISLEX_CRISISLEXREC OR theme:KILL)'
)

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)

# 진단을 위한 마지막 호출 메타데이터 (페이지에서 expander로 노출)
_DIAG: List[dict] = []


def _normalize(title: str) -> str:
    return _PUNCT.sub("", (title or "").lower()).strip()


def _hash(title: str) -> str:
    return hashlib.sha1(_normalize(title).encode("utf-8")).hexdigest()


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def _fetch_window(
    query: str,
    start: datetime,
    end: datetime,
    max_records: int = 250,
    sort: str = "DateDesc",
) -> Tuple[pd.DataFrame, Optional[str]]:
    """단일 윈도우 호출. (DataFrame, error_message_or_None) 반환."""
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "startdatetime": _fmt(start),
        "enddatetime": _fmt(end),
        "maxrecords": max_records,
        "sort": sort,
    }
    sess = get_session()
    try:
        # requests가 자동으로 RFC 3986 인코딩 처리 — 수동 urlencode보다 안전
        resp = sess.get(GDELT_DOC_URL, params=params, timeout=30)
    except Exception as e:
        return pd.DataFrame(), f"network: {type(e).__name__}: {str(e)[:120]}"

    if resp.status_code != 200:
        snippet = (resp.text or "")[:160]
        return pd.DataFrame(), f"HTTP {resp.status_code}: {snippet}"

    body = (resp.text or "").strip()
    if not body:
        return pd.DataFrame(), "empty body"
    if not body.startswith("{") and not body.startswith("["):
        return pd.DataFrame(), f"non-JSON: {body[:160]}"

    try:
        payload = resp.json()
    except ValueError as e:
        return pd.DataFrame(), f"JSON parse: {str(e)[:80]}"

    if not isinstance(payload, dict):
        return pd.DataFrame(), f"unexpected payload type: {type(payload).__name__}"

    arts = payload.get("articles", [])
    if not arts:
        return pd.DataFrame(), None  # 빈 결과는 정상 — 그 윈도우엔 기사가 없음

    rows = []
    for a in arts:
        seen = a.get("seendate")
        try:
            seen_dt = (
                datetime.strptime(seen, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                if seen else None
            )
        except ValueError:
            seen_dt = None
        rows.append({
            "datetime": seen_dt,
            "date": seen_dt.date() if seen_dt else None,
            "title": a.get("title"),
            "url": a.get("url"),
            "domain": a.get("domain"),
            "language": a.get("language"),
            "sourcecountry": a.get("sourcecountry"),
            "image": a.get("socialimage"),
        })
    return pd.DataFrame(rows), None


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_articles_v2(
    start: date,
    end: date,
    include_korean: bool = True,
    window_days: int = 7,
) -> Tuple[pd.DataFrame, List[dict]]:
    """기간 내 미-이란 분쟁 기사 수집.

    7일 슬라이딩 윈도우로 페이지네이션 — 90일 기준 영문 13회 + 한국어 13회 호출.
    GDELT의 비공식 레이트 제한(약 5초당 1건) 회피를 위해 호출 간 0.3s sleep.

    Returns:
        (articles_df, diagnostics) — 각 호출의 결과·에러 메타데이터 포함.

    Note: v2 — 이전 버전(단일 DataFrame 반환)과 캐시 키 분리.
    """
    if end < start:
        return pd.DataFrame(), [{"error": "end < start"}]

    parts: List[pd.DataFrame] = []
    diag: List[dict] = []
    cursor = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc)

    while cursor < end_dt:
        window_end = min(cursor + timedelta(days=window_days), end_dt)
        calls = [("en", QUERY_EN)]
        if include_korean:
            calls.append(("ko", QUERY_KO))
        for lang_code, q in calls:
            df, err = _fetch_window(q, cursor, window_end)
            diag.append({
                "lang": lang_code,
                "start": cursor.strftime("%Y-%m-%d"),
                "end": window_end.strftime("%Y-%m-%d"),
                "rows": int(df.shape[0]),
                "error": err,
            })
            if not df.empty:
                parts.append(df)
            time.sleep(0.3)  # 레이트 제한 회피
        cursor = window_end

    if not parts:
        return pd.DataFrame(), diag
    df = pd.concat(parts, ignore_index=True)
    return _dedupe(df), diag


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "title" not in df.columns:
        return df
    df = df.copy()
    df["_hash"] = df["title"].fillna("").map(_hash)
    df = df.sort_values("datetime").drop_duplicates(subset=["_hash"], keep="first")
    df = df.drop(columns=["_hash"])
    df = df.dropna(subset=["datetime", "title"]).reset_index(drop=True)
    return df


def daily_volume(df: pd.DataFrame) -> pd.Series:
    if df.empty or "date" not in df.columns:
        return pd.Series(dtype=int)
    s = df.groupby("date").size().sort_index()
    s.index = pd.to_datetime(s.index)
    return s


def escalation_days(volume: pd.Series, z_threshold: float = 2.0) -> List[date]:
    """일별 보도량 평균+zσ 초과 → 에스컬레이션 일자."""
    if volume.empty or len(volume) < 5:
        return []
    mean = volume.mean()
    std = volume.std(ddof=0)
    if std == 0 or pd.isna(std):
        return []
    z = (volume - mean) / std
    days = volume.index[z > z_threshold]
    return [d.date() if hasattr(d, "date") else d for d in days]
