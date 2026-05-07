"""
Configuration for Macro Sentinel.

NOTE: This is a placeholder reconstructed from macro_sentinel.py imports.
If your local config.py uses different FRED series IDs, ticker lists, or
lookback windows, paste those values here and re-commit.

Secrets (FRED_API_KEY) are loaded from environment variables. In GitHub
Actions, set them as repository Secrets and they are injected via the
workflow's `env:` block.
"""
import os

# --- Secrets (env-driven) ---
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# --- FRED series IDs (verify against your local config) ---
FRED_SERIES = {
    "TGA":         "WTREGEN",              # Treasury General Account, weekly, $M
    "WRESBAL":     "WRESBAL",              # Reserve Balances of Depository Institutions, weekly
    "STLFSI4":     "STLFSI4",              # St. Louis Fed Financial Stress Index, weekly
    "T10Y2Y":      "T10Y2Y",               # 10Y - 2Y Treasury yield spread, daily
    "SOFR":        "SOFR",                 # Secured Overnight Financing Rate
    "IORB":        "IORB",                 # Interest on Reserve Balances
    "RRP":         "RRPONTSYD",            # Overnight Reverse Repo, daily, $B
    "DXY":         "DTWEXBGS",             # Trade-Weighted US Dollar Index (broad)
    "VIX":         "VIXCLS",               # CBOE Volatility Index, daily
    "MMF":         "WRMFNS",               # Money Market Mutual Fund Assets, weekly
    "MARGIN_DEBT": "BOGZ1FL663067003Q",    # Margin debt (FINRA, quarterly)
}

# --- Big tech tickers tracked for insider trading ---
INSIDER_TICKERS = ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA"]

# --- ETF used as defensive proxy for sector rotation ---
CONSUMER_STAPLES_ETF = "XLP"

# --- Output directory (relative to this file) ---
REPORT_DIR = "reports"

# --- Default lookback for FRED series (weeks) ---
LOOKBACK_WEEKS = 26
