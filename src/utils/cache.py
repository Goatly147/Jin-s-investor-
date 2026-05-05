"""디스크 캐시(joblib) + retry-equipped requests.Session."""

from pathlib import Path

import requests
from joblib import Memory
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

memory = Memory(location=str(CACHE_DIR), verbose=0)


def get_session(retries: int = 3, backoff: float = 0.5, timeout: int = 30) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "JinsInvestor/0.1 (+streamlit)"})
    session.request_timeout = timeout  # type: ignore[attr-defined]
    return session
