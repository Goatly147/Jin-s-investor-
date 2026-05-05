"""GDELT 2.0 DOC API 클라이언트 — 미-이란 분쟁 뉴스 자동 수집."""

import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from typing import List
from urllib.parse import urlencode

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


def _normalize(title: str) -> str:
    return _PUNCT.sub("", (title or "").lower()).strip()


def _hash(title: str) -> str:
    return hashlib.sha1(_normalize(title).encode("utf-8")).hexdigest()


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def _fetch_window(query: str, start: datetime, end: datetime, max_records: int = 250) -> pd.DataFrame:
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "startdatetime": _fmt(start),
        "enddatetime": _fmt(end),
        "maxrecords": max_records,
        "sort": "HybridRel",
    }
    safe_chars = ':()" '
    url = f"{GDELT_DOC_URL}?{urlencode(params, safe=safe_chars)}"
    sess = get_session()
    try:
        resp = sess.get(url, timeout=30)
        if resp.status_code != 200:
            return pd.DataFrame()
        try:
            payload = resp.json()
        except ValueError:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

    arts = payload.get("articles", []) if isinstance(payload, dict) else []
    if not arts:
        return pd.DataFrame()

    rows = []
    for a in arts:
        seen = a.get("seendate")
        try:
            seen_dt = datetime.strptime(seen, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc) if seen else None
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
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_articles(start: date, end: date, include_korean: bool = True) -> pd.DataFrame:
    """기간 내 미-이란 분쟁 기사 수집 — 24h 슬라이딩 윈도우로 페이지네이션."""
    if end < start:
        return pd.DataFrame()

    parts: List[pd.DataFrame] = []
    cursor = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc)

    while cursor < end_dt:
        window_end = min(cursor + timedelta(days=1), end_dt)
        parts.append(_fetch_window(QUERY_EN, cursor, window_end, max_records=250))
        if include_korean:
            parts.append(_fetch_window(QUERY_KO, cursor, window_end, max_records=250))
        cursor = window_end

    if not parts:
        return pd.DataFrame()
    df = pd.concat([p for p in parts if not p.empty], ignore_index=True) if any(not p.empty for p in parts) else pd.DataFrame()
    if df.empty:
        return df
    return _dedupe(df)


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
