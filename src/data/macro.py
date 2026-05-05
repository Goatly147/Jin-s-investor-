"""거시지표 데이터 — FRED CSV (키 불필요), Shiller CAPE xls."""

from io import BytesIO, StringIO
from typing import Optional

import pandas as pd
import streamlit as st

from src.utils.cache import get_session

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
SHILLER_XLS = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"


@st.cache_data(ttl=86400, show_spinner=False)
def get_fred_series(series_id: str) -> pd.Series:
    """FRED 무료 CSV. 컬럼명은 series_id, 인덱스는 DATE."""
    sess = get_session()
    url = FRED_CSV.format(series_id=series_id)
    try:
        resp = sess.get(url, timeout=30)
        if resp.status_code != 200:
            return pd.Series(dtype=float, name=series_id)
        df = pd.read_csv(StringIO(resp.text))
    except Exception:
        return pd.Series(dtype=float, name=series_id)

    if df.empty or "DATE" not in df.columns or series_id not in df.columns:
        return pd.Series(dtype=float, name=series_id)
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["DATE"]).set_index("DATE")
    s = pd.to_numeric(df[series_id], errors="coerce").dropna()
    s.name = series_id
    return s


@st.cache_data(ttl=86400, show_spinner=False)
def get_shiller_cape() -> Optional[pd.Series]:
    """Shiller 공식 xls의 CAPE 컬럼."""
    sess = get_session()
    try:
        resp = sess.get(SHILLER_XLS, timeout=60)
        if resp.status_code != 200:
            return None
        df = pd.read_excel(BytesIO(resp.content), sheet_name="Data", skiprows=7)
    except Exception:
        return None

    cape_col = None
    for c in df.columns:
        cl = str(c).strip().lower()
        if cl in ("cape", "cape ratio") or cl.startswith("cape"):
            cape_col = c
            break
    date_col = None
    for c in df.columns:
        if str(c).strip().lower() == "date":
            date_col = c
            break
    if cape_col is None or date_col is None:
        return None

    raw = df[[date_col, cape_col]].dropna()

    def _to_date(v):
        try:
            sv = str(v)
            if "." in sv:
                year, frac = sv.split(".")
                month = int((frac + "0")[:2])
                month = max(1, min(12, month))
                return pd.Timestamp(year=int(year), month=month, day=1)
            return pd.Timestamp(int(float(sv)), 1, 1)
        except Exception:
            return pd.NaT

    raw["_date"] = raw[date_col].map(_to_date)
    raw = raw.dropna(subset=["_date"]).set_index("_date").sort_index()
    s = pd.to_numeric(raw[cape_col], errors="coerce").dropna()
    s.name = "CAPE"
    return s
