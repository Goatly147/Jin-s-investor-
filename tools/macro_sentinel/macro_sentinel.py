"""
Macro Sentinel - Daily Market Sentiment Dashboard
Collects macro indicators and generates an HTML sentiment report.
"""

import os
import sys
import json
import datetime
import traceback
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from fredapi import Fred

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    FRED_API_KEY, FRED_SERIES, INSIDER_TICKERS,
    CONSUMER_STAPLES_ETF, REPORT_DIR, LOOKBACK_WEEKS
)

fred = Fred(api_key=FRED_API_KEY)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ============================================================
# Data Collection Functions
# ============================================================

def fetch_fred_series(series_id, lookback_days=None, retries=3):
    """Fetch a FRED series, returning a pandas Series. Retries on server errors."""
    import time
    if lookback_days is None:
        lookback_days = LOOKBACK_WEEKS * 7
    start = datetime.date.today() - datetime.timedelta(days=lookback_days)
    for attempt in range(retries):
        try:
            data = fred.get_series(series_id, observation_start=start)
            return data.dropna()
        except Exception as e:
            if "Internal Server Error" in str(e) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            print(f"[WARN] FRED {series_id} fetch failed: {e}")
            return pd.Series(dtype=float)
    return pd.Series(dtype=float)


def fetch_all_fred():
    """Fetch all configured FRED series."""
    results = {}
    for name, sid in FRED_SERIES.items():
        # Quarterly series need longer lookback
        days = 730 if name in ("MMF", "MARGIN_DEBT") else LOOKBACK_WEEKS * 7
        results[name] = fetch_fred_series(sid, lookback_days=days)
    return results


def fetch_fear_greed():
    """Fetch CNN Fear & Greed Index via their API endpoint."""
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            score = data.get("fear_and_greed", {}).get("score", None)
            rating = data.get("fear_and_greed", {}).get("rating", "N/A")
            return {"score": round(score, 1) if score else None, "rating": rating}
    except Exception as e:
        print(f"[WARN] Fear & Greed fetch failed: {e}")
    return {"score": None, "rating": "N/A"}


def fetch_insider_trading():
    """Scrape openinsider.com for insider trades of target tickers."""
    results = {}
    for ticker in INSIDER_TICKERS:
        try:
            # tf=6 = last 6 months, st=1 = include derivative transactions
            url = f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&st=0&lt=0&lk=&tf=6&tfd=&tft=&isd=&ied=&sicMin=&sicMax=&mc=&mci=&a=&an=&at=&sp=&ipo=&ipoMin=&ipoMax="
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", class_="tinytable")
            if not table:
                results[ticker] = {"buys": 0, "sells": 0, "net_shares": 0, "transactions": []}
                continue
            rows = table.find_all("tr")[1:]  # skip header
            buys, sells = 0, 0
            net_shares = 0
            transactions = []
            for row in rows[:20]:  # last 20 transactions
                cols = row.find_all("td")
                if len(cols) < 12:
                    continue
                # tinytable columns: X, Filing Date, Trade Date, Ticker, Insider Name, Title, Trade Type, Price, Qty, Owned, %Own, Value, ...
                trade_type = cols[6].get_text(strip=True)
                qty_text = cols[8].get_text(strip=True).replace(",", "").replace("+", "")
                try:
                    qty = int(qty_text)
                except ValueError:
                    qty = 0
                if "P - Purchase" in trade_type:
                    buys += 1
                    net_shares += abs(qty)
                elif "S - Sale" in trade_type:
                    sells += 1
                    net_shares -= abs(qty)
                transactions.append({
                    "date": cols[2].get_text(strip=True),
                    "insider": cols[4].get_text(strip=True)[:30],
                    "type": trade_type,
                    "shares": qty,
                })
            results[ticker] = {
                "buys": buys,
                "sells": sells,
                "net_shares": net_shares,
                "transactions": transactions[:5],
            }
        except Exception as e:
            print(f"[WARN] Insider {ticker} fetch failed: {e}")
            results[ticker] = {"buys": 0, "sells": 0, "net_shares": 0, "transactions": []}
    return results


def fetch_sofr_iorb_direct():
    """Fetch SOFR and IORB directly from NY Fed / FRED as fallback."""
    sofr, iorb = pd.Series(dtype=float), pd.Series(dtype=float)
    try:
        # Try FRED with different series
        sofr = fetch_fred_series("SOFR", lookback_days=90)
        if sofr.empty:
            # Fallback: try EFFR (effective federal funds rate) as proxy
            sofr = fetch_fred_series("EFFR", lookback_days=90)
    except Exception:
        pass
    try:
        iorb = fetch_fred_series("IORB", lookback_days=90)
        if iorb.empty:
            # Fallback: IOER (older series)
            iorb = fetch_fred_series("IOER", lookback_days=90)
    except Exception:
        pass
    return sofr, iorb


def fetch_etf_prices(ticker, period="3mo"):
    """Fetch ETF price data from Yahoo Finance."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={period}&interval=1d"
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0",
        }, timeout=15)
        data = resp.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        dates = [datetime.datetime.fromtimestamp(t).date() for t in timestamps]
        return pd.Series(closes, index=pd.DatetimeIndex(dates))
    except Exception as e:
        print(f"[WARN] Yahoo {ticker} fetch failed: {e}")
        return pd.Series(dtype=float)


def fetch_primary_dealer():
    """Fetch Primary Dealer net positioning data from NY Fed Markets API."""
    try:
        # PDPOSGST-TOT = US Treasury Securities net position (Long - Short), in millions USD
        url = "https://markets.newyorkfed.org/api/pd/get/SBN2024/timeseries/PDPOSGST-TOT.csv"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {"status": "unavailable", "series": pd.Series(dtype=float)}
        lines = resp.text.strip().split("\n")
        dates, values = [], []
        for line in lines[1:]:  # skip header
            parts = line.replace('"', '').split(",")
            if len(parts) >= 3 and parts[2].strip() not in ("", "*"):
                dates.append(pd.Timestamp(parts[0].strip()))
                values.append(float(parts[2].strip()))
        if not dates:
            return {"status": "unavailable", "series": pd.Series(dtype=float)}
        series = pd.Series(values, index=pd.DatetimeIndex(dates)).sort_index()
        return {"status": "fetched", "series": series}
    except Exception as e:
        print(f"[WARN] Primary Dealer fetch failed: {e}")
        return {"status": "unavailable", "series": pd.Series(dtype=float)}


def analyze_primary_dealer(pd_data):
    """Analyze Primary Dealer net positioning for risk signals."""
    if pd_data["status"] != "fetched" or pd_data["series"].empty:
        return {"signal": "NEUTRAL", "detail": "NY Fed data unavailable"}
    series = pd_data["series"]
    if len(series) < 4:
        return {"signal": "NEUTRAL", "detail": "Insufficient history"}

    latest = series.iloc[-1]
    prev_4w = series.iloc[-4] if len(series) >= 4 else series.iloc[0]
    prev_12w = series.iloc[-12] if len(series) >= 12 else series.iloc[0]
    change_4w = latest - prev_4w
    change_4w_pct = (change_4w / prev_4w) * 100 if prev_4w != 0 else 0
    change_12w = latest - prev_12w
    change_12w_pct = (change_12w / prev_12w) * 100 if prev_12w != 0 else 0

    # Peak detection: if position declining from recent high
    recent_high = series.tail(12).max()
    off_peak_pct = ((latest / recent_high) - 1) * 100 if recent_high != 0 else 0

    latest_b = latest / 1000  # millions to billions
    change_4w_b = change_4w / 1000

    if change_4w_pct < -10 and off_peak_pct < -10:
        return {"signal": "BEARISH",
                "detail": f"Dealers cutting positions: ${latest_b:.0f}B ({change_4w_pct:+.1f}% 4w), {off_peak_pct:.1f}% off peak - support withdrawn"}
    elif change_4w_pct < -5:
        return {"signal": "CAUTION",
                "detail": f"Dealer positioning declining: ${latest_b:.0f}B ({change_4w_pct:+.1f}% 4w, {change_12w_pct:+.1f}% 12w)"}
    elif change_4w_pct > 5:
        return {"signal": "BULLISH",
                "detail": f"Dealers increasing exposure: ${latest_b:.0f}B ({change_4w_pct:+.1f}% 4w, {change_12w_pct:+.1f}% 12w)"}
    else:
        return {"signal": "NEUTRAL",
                "detail": f"Dealer positioning stable: ${latest_b:.0f}B ({change_4w_pct:+.1f}% 4w, {change_12w_pct:+.1f}% 12w)"}


# ============================================================
# Sentiment Analysis Engine
# ============================================================

def analyze_wresbal(series):
    """Analyze bank reserve velocity (WRESBAL)."""
    if len(series) < 8:
        return {"signal": "NEUTRAL", "detail": "Insufficient data"}
    recent_4w = series.iloc[-4:]
    prev_4w = series.iloc[-8:-4]
    recent_change = recent_4w.iloc[-1] - recent_4w.iloc[0]
    prev_change = prev_4w.iloc[-1] - prev_4w.iloc[0]
    velocity_ratio = recent_change / max(abs(prev_change), 1)

    if recent_change > 0 and velocity_ratio >= 0.8:
        return {"signal": "BULLISH", "detail": f"Reserve velocity maintained (+{recent_change/1e9:.1f}B, ratio: {velocity_ratio:.2f})"}
    elif recent_change < 0:
        return {"signal": "BEARISH", "detail": f"Reserves declining ({recent_change/1e9:.1f}B)"}
    else:
        return {"signal": "NEUTRAL", "detail": f"Velocity slowing (ratio: {velocity_ratio:.2f})"}


def analyze_stlfsi(series):
    """Analyze Financial Stress Index."""
    if series.empty:
        return {"signal": "NEUTRAL", "detail": "No data"}
    latest = series.iloc[-1]
    below_zero_count = (series.tail(12) < 0).sum()

    if latest < -1.0 and below_zero_count >= 10:
        return {"signal": "CAUTION", "detail": f"Extreme calm ({latest:.2f}), below 0 for {below_zero_count}/12 weeks - stress cycle may be imminent"}
    elif latest < 0:
        return {"signal": "BULLISH", "detail": f"Low stress ({latest:.2f})"}
    elif latest > 1.5:
        return {"signal": "BEARISH", "detail": f"High stress ({latest:.2f})"}
    else:
        return {"signal": "NEUTRAL", "detail": f"Moderate stress ({latest:.2f})"}


def analyze_yield_curve(series):
    """Analyze 10Y-2Y spread normalization speed."""
    if len(series) < 20:
        return {"signal": "NEUTRAL", "detail": "Insufficient data"}
    latest = series.iloc[-1]
    min_val = series.min()
    # Check if rapidly normalizing from inversion
    was_inverted = min_val < 0
    if was_inverted and latest > 0:
        normalization_speed = latest - series.iloc[-20]
        if normalization_speed > 0.5:
            return {"signal": "BEARISH", "detail": f"Rapid normalization from inversion (+{normalization_speed:.2f}pp in 20d) - recession warning"}
        else:
            return {"signal": "CAUTION", "detail": f"Normalizing from inversion (spread: {latest:.2f}%)"}
    elif latest < 0:
        return {"signal": "CAUTION", "detail": f"Yield curve inverted ({latest:.2f}%)"}
    else:
        return {"signal": "BULLISH", "detail": f"Normal yield curve ({latest:.2f}%)"}


def analyze_sofr_iorb(sofr_series, iorb_series):
    """Analyze SOFR-IORB spread for interbank trust."""
    if sofr_series.empty or iorb_series.empty:
        return {"signal": "NEUTRAL", "detail": "No data"}
    # Align dates
    common = sofr_series.index.intersection(iorb_series.index)
    if len(common) < 5:
        # Try using latest values
        sofr_val = sofr_series.iloc[-1]
        iorb_val = iorb_series.iloc[-1]
        spread = sofr_val - iorb_val
    else:
        sofr_aligned = sofr_series.loc[common]
        iorb_aligned = iorb_series.loc[common]
        spread_series = sofr_aligned - iorb_aligned
        spread = spread_series.iloc[-1]
        # Check if spread is widening and persistent
        if len(spread_series) >= 10:
            avg_recent = spread_series.tail(5).mean()
            avg_prior = spread_series.tail(10).head(5).mean()
            if avg_recent > avg_prior + 0.02:
                return {"signal": "BEARISH", "detail": f"SOFR-IORB spread widening ({spread:.3f}%) - interbank trust deteriorating"}

    if abs(spread) > 0.05:
        return {"signal": "BEARISH", "detail": f"SOFR-IORB spread elevated ({spread:.3f}%)"}
    elif abs(spread) > 0.02:
        return {"signal": "CAUTION", "detail": f"SOFR-IORB spread moderate ({spread:.3f}%)"}
    else:
        return {"signal": "BULLISH", "detail": f"SOFR-IORB spread tight ({spread:.3f}%) - normal interbank trust"}


def analyze_tga(series):
    """Analyze Treasury General Account balance."""
    if len(series) < 4:
        return {"signal": "NEUTRAL", "detail": "Insufficient data"}
    latest = series.iloc[-1]
    prev = series.iloc[-4]
    change = latest - prev
    change_pct = (change / prev) * 100 if prev != 0 else 0

    # TGA is in millions of dollars in FRED
    if change < -50_000:  # TGA drawdown > $50B
        return {"signal": "BULLISH", "detail": f"TGA drawdown ${change/1e3:.0f}B ({change_pct:.1f}%) - liquidity injection into market"}
    elif change > 50_000:
        return {"signal": "BEARISH", "detail": f"TGA buildup +${change/1e3:.0f}B ({change_pct:.1f}%) - liquidity drain from market"}
    else:
        return {"signal": "NEUTRAL", "detail": f"TGA stable (${latest/1e3:.0f}B, change: {change_pct:.1f}%)"}


def analyze_dxy_quality(dxy_series, vix_series):
    """Analyze whether dollar strength is fear-driven or growth-driven."""
    if dxy_series.empty:
        return {"signal": "NEUTRAL", "detail": "No DXY data"}

    dxy_latest = dxy_series.iloc[-1]
    dxy_change = 0
    if len(dxy_series) >= 20:
        dxy_change = ((dxy_latest / dxy_series.iloc[-20]) - 1) * 100

    if vix_series.empty:
        if dxy_change > 2:
            return {"signal": "CAUTION", "detail": f"DXY rising (+{dxy_change:.1f}%), cannot determine quality without VIX"}
        return {"signal": "NEUTRAL", "detail": f"DXY: {dxy_latest:.1f} ({dxy_change:+.1f}%)"}

    vix_latest = vix_series.iloc[-1]
    vix_change = 0
    if len(vix_series) >= 20:
        vix_change = ((vix_latest / vix_series.iloc[-20]) - 1) * 100

    if dxy_change > 1.5 and vix_change > 20:
        return {"signal": "BEARISH", "detail": f"Fear Dollar: DXY +{dxy_change:.1f}% with VIX +{vix_change:.0f}% - risk-off flight to safety"}
    elif dxy_change > 1.5 and vix_change < 5:
        return {"signal": "BULLISH", "detail": f"Growth Dollar: DXY +{dxy_change:.1f}% with stable VIX - healthy demand"}
    elif dxy_change < -1.5:
        return {"signal": "NEUTRAL", "detail": f"Dollar weakening ({dxy_change:.1f}%)"}
    else:
        return {"signal": "NEUTRAL", "detail": f"DXY stable ({dxy_change:+.1f}%), VIX: {vix_latest:.1f}"}


def analyze_rrp(series):
    """Analyze Reverse Repo facility usage."""
    if len(series) < 10:
        return {"signal": "NEUTRAL", "detail": "Insufficient data"}
    latest = series.iloc[-1]
    avg_recent = series.tail(5).mean()
    avg_prior = series.tail(20).head(10).mean() if len(series) >= 20 else series.mean()
    change_pct = ((avg_recent / avg_prior) - 1) * 100 if avg_prior != 0 else 0

    if change_pct < -20:
        return {"signal": "BULLISH", "detail": f"RRP declining ({change_pct:.0f}%) - liquidity flowing into markets, ${latest/1e9:.0f}B"}
    elif change_pct > 20:
        return {"signal": "BEARISH", "detail": f"RRP surging (+{change_pct:.0f}%) - capital seeking safe haven, ${latest/1e9:.0f}B"}
    else:
        return {"signal": "NEUTRAL", "detail": f"RRP stable (${latest/1e9:.0f}B, {change_pct:+.0f}%)"}


def analyze_sector_rotation(xlp_series, luxury_series):
    """Analyze Consumer Staples vs Luxury sector rotation."""
    if xlp_series.empty or luxury_series.empty:
        return {"signal": "NEUTRAL", "detail": "Insufficient ETF data"}

    # Compare recent performance
    xlp_perf = 0
    lux_perf = 0
    lookback = min(20, len(xlp_series) - 1, len(luxury_series) - 1)
    if lookback < 5:
        return {"signal": "NEUTRAL", "detail": "Insufficient history"}

    xlp_perf = ((xlp_series.iloc[-1] / xlp_series.iloc[-lookback]) - 1) * 100
    lux_perf = ((luxury_series.iloc[-1] / luxury_series.iloc[-lookback]) - 1) * 100

    if xlp_perf < -1 and lux_perf > 1:
        return {"signal": "BULLISH", "detail": f"Risk-on rotation: Staples {xlp_perf:+.1f}% vs Luxury {lux_perf:+.1f}% - capital moving to growth"}
    elif xlp_perf > 1 and lux_perf < -1:
        return {"signal": "BEARISH", "detail": f"Risk-off rotation: Staples {xlp_perf:+.1f}% vs Luxury {lux_perf:+.1f}% - defensive positioning"}
    else:
        return {"signal": "NEUTRAL", "detail": f"Staples {xlp_perf:+.1f}% vs Luxury {lux_perf:+.1f}%"}


def analyze_fear_greed(fg_data):
    """Analyze CNN Fear & Greed Index."""
    score = fg_data.get("score")
    rating = fg_data.get("rating", "N/A")
    if score is None:
        return {"signal": "NEUTRAL", "detail": "No data available"}
    if score >= 80:
        return {"signal": "BEARISH", "detail": f"Extreme Greed ({score}) - contrarian sell signal, crowd euphoria"}
    elif score >= 60:
        return {"signal": "CAUTION", "detail": f"Greed ({score}) - market optimism elevated"}
    elif score <= 20:
        return {"signal": "BULLISH", "detail": f"Extreme Fear ({score}) - contrarian buy signal, capitulation"}
    elif score <= 40:
        return {"signal": "CAUTION", "detail": f"Fear ({score}) - market anxiety"}
    else:
        return {"signal": "NEUTRAL", "detail": f"Neutral ({score}) - {rating}"}


def analyze_insider_trading(insider_data):
    """Analyze insider trading across big tech."""
    total_buys = sum(d["buys"] for d in insider_data.values())
    total_sells = sum(d["sells"] for d in insider_data.values())
    total_net = sum(d["net_shares"] for d in insider_data.values())

    heavy_sellers = [t for t, d in insider_data.items() if d["sells"] > d["buys"] + 2]

    if total_sells > total_buys * 3 and len(heavy_sellers) >= 3:
        return {"signal": "BEARISH", "detail": f"Heavy insider selling: {total_sells} sells vs {total_buys} buys across {', '.join(heavy_sellers)}"}
    elif total_sells > total_buys * 2:
        return {"signal": "CAUTION", "detail": f"Elevated insider selling ({total_sells} sells vs {total_buys} buys)"}
    elif total_buys > total_sells:
        return {"signal": "BULLISH", "detail": f"Net insider buying ({total_buys} buys vs {total_sells} sells)"}
    else:
        return {"signal": "NEUTRAL", "detail": f"Insider activity balanced ({total_buys} buys / {total_sells} sells)"}


# ============================================================
# HTML Report Generator
# ============================================================

SIGNAL_COLORS = {
    "BULLISH": ("#10b981", "#d1fae5", "BULLISH"),
    "BEARISH": ("#ef4444", "#fee2e2", "BEARISH"),
    "CAUTION": ("#f59e0b", "#fef3c7", "CAUTION"),
    "NEUTRAL": ("#6b7280", "#f3f4f6", "NEUTRAL"),
}


def generate_html(indicators, insider_data, fear_greed, date_str):
    """Generate the HTML dashboard report."""

    # Count signals
    signal_counts = {"BULLISH": 0, "BEARISH": 0, "CAUTION": 0, "NEUTRAL": 0}
    for ind in indicators.values():
        signal_counts[ind["signal"]] = signal_counts.get(ind["signal"], 0) + 1

    total = sum(signal_counts.values())
    if total > 0:
        bull_pct = (signal_counts["BULLISH"] / total) * 100
        bear_pct = (signal_counts["BEARISH"] / total) * 100
    else:
        bull_pct = bear_pct = 0

    if bull_pct > 50:
        overall = "BULLISH"
        overall_text = "Risk-On: Market conditions favor growth assets"
    elif bear_pct > 40:
        overall = "BEARISH"
        overall_text = "Risk-Off: Defensive positioning recommended"
    elif signal_counts["CAUTION"] >= 3:
        overall = "CAUTION"
        overall_text = "Caution: Mixed signals, transition period"
    else:
        overall = "NEUTRAL"
        overall_text = "Neutral: No dominant trend signal"

    overall_color, overall_bg, _ = SIGNAL_COLORS[overall]

    # Build indicator rows
    indicator_rows = ""
    category_map = {
        "Primary Dealer": "liquidity",
        "TGA": "liquidity",
        "WRESBAL": "liquidity",
        "STLFSI4": "stress",
        "Sector Rotation": "capital_flow",
        "DXY Quality": "capital_flow",
        "SOFR-IORB": "system_trust",
        "RRP": "liquidity",
        "Yield Curve": "recession",
        "Fear & Greed": "sentiment",
        "Insider Trading": "sentiment",
    }

    category_labels = {
        "liquidity": "Liquidity & Reserves",
        "stress": "Financial Stress",
        "capital_flow": "Capital Flow & Rotation",
        "system_trust": "System Trust",
        "recession": "Recession Indicators",
        "sentiment": "Investor Sentiment",
    }

    # Group by category
    grouped = {}
    for name, data in indicators.items():
        cat = category_map.get(name, "other")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append((name, data))

    for cat_key in ["liquidity", "stress", "capital_flow", "system_trust", "recession", "sentiment"]:
        if cat_key not in grouped:
            continue
        label = category_labels.get(cat_key, cat_key)
        indicator_rows += f'<tr><td colspan="3" style="background:#1e293b;color:#94a3b8;font-weight:600;padding:12px 16px;font-size:0.85em;text-transform:uppercase;letter-spacing:1px;">{label}</td></tr>\n'
        for name, data in grouped[cat_key]:
            color, bg, label_text = SIGNAL_COLORS[data["signal"]]
            indicator_rows += f'''<tr>
<td style="padding:12px 16px;font-weight:500;color:#e2e8f0;">{name}</td>
<td style="padding:12px 16px;"><span style="background:{bg};color:{color};padding:4px 12px;border-radius:12px;font-weight:600;font-size:0.85em;">{label_text}</span></td>
<td style="padding:12px 16px;color:#94a3b8;font-size:0.9em;">{data["detail"]}</td>
</tr>\n'''

    # Insider detail table
    insider_rows = ""
    for ticker in INSIDER_TICKERS:
        d = insider_data.get(ticker, {"buys": 0, "sells": 0, "net_shares": 0})
        net_color = "#10b981" if d["net_shares"] > 0 else "#ef4444" if d["net_shares"] < 0 else "#6b7280"
        insider_rows += f'''<tr>
<td style="padding:8px 12px;color:#e2e8f0;font-weight:600;">{ticker}</td>
<td style="padding:8px 12px;color:#10b981;">{d["buys"]}</td>
<td style="padding:8px 12px;color:#ef4444;">{d["sells"]}</td>
<td style="padding:8px 12px;color:{net_color};font-weight:600;">{d["net_shares"]:+,}</td>
</tr>\n'''

    fg_score = fear_greed.get("score", "N/A")
    fg_rating = fear_greed.get("rating", "N/A")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Macro Sentinel - {date_str}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',system-ui,-apple-system,sans-serif; }}
.container {{ max-width:1100px; margin:0 auto; padding:24px; }}
.header {{ text-align:center; margin-bottom:32px; }}
.header h1 {{ font-size:1.8em; color:#f8fafc; margin-bottom:8px; }}
.header .date {{ color:#64748b; font-size:1em; }}
.overall-box {{ background:linear-gradient(135deg, {overall_bg}22, {overall_bg}11); border:2px solid {overall_color}44; border-radius:16px; padding:24px; text-align:center; margin-bottom:32px; }}
.overall-box .signal {{ font-size:2em; font-weight:700; color:{overall_color}; }}
.overall-box .desc {{ color:#94a3b8; margin-top:8px; }}
.stats {{ display:flex; gap:16px; justify-content:center; margin-bottom:32px; flex-wrap:wrap; }}
.stat-card {{ background:#1e293b; border-radius:12px; padding:16px 24px; text-align:center; min-width:120px; }}
.stat-card .num {{ font-size:1.5em; font-weight:700; }}
.stat-card .label {{ color:#64748b; font-size:0.85em; margin-top:4px; }}
table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:12px; overflow:hidden; margin-bottom:24px; }}
table th {{ background:#0f172a; color:#64748b; padding:12px 16px; text-align:left; font-size:0.85em; text-transform:uppercase; letter-spacing:1px; }}
table td {{ border-bottom:1px solid #334155; }}
table tr:last-child td {{ border-bottom:none; }}
.section-title {{ color:#f8fafc; font-size:1.3em; font-weight:600; margin:32px 0 16px; }}
.fg-box {{ background:#1e293b; border-radius:12px; padding:24px; text-align:center; margin-bottom:24px; }}
.fg-score {{ font-size:3em; font-weight:700; }}
.fg-label {{ color:#64748b; font-size:1em; margin-top:4px; }}
.footer {{ text-align:center; color:#475569; font-size:0.8em; margin-top:40px; padding-top:20px; border-top:1px solid #1e293b; }}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>MACRO SENTINEL</h1>
<div class="date">{date_str} Daily Market Sentiment Report</div>
</div>

<div class="overall-box">
<div class="signal">{overall}</div>
<div class="desc">{overall_text}</div>
</div>

<div class="stats">
<div class="stat-card"><div class="num" style="color:#10b981">{signal_counts["BULLISH"]}</div><div class="label">Bullish</div></div>
<div class="stat-card"><div class="num" style="color:#f59e0b">{signal_counts["CAUTION"]}</div><div class="label">Caution</div></div>
<div class="stat-card"><div class="num" style="color:#ef4444">{signal_counts["BEARISH"]}</div><div class="label">Bearish</div></div>
<div class="stat-card"><div class="num" style="color:#6b7280">{signal_counts["NEUTRAL"]}</div><div class="label">Neutral</div></div>
</div>

<div class="section-title">Indicator Dashboard</div>
<table>
<thead><tr>
<th style="width:200px;">Indicator</th>
<th style="width:120px;">Signal</th>
<th>Analysis</th>
</tr></thead>
<tbody>
{indicator_rows}
</tbody>
</table>

<div class="section-title">Fear & Greed Index</div>
<div class="fg-box">
<div class="fg-score" style="color:{'#ef4444' if fg_score and fg_score >= 60 else '#10b981' if fg_score and fg_score <= 40 else '#f59e0b'}">{fg_score}</div>
<div class="fg-label">{fg_rating}</div>
</div>

<div class="section-title">Big Tech Insider Trading (Last 3 Months)</div>
<table>
<thead><tr>
<th>Ticker</th>
<th>Buys</th>
<th>Sells</th>
<th>Net Shares</th>
</tr></thead>
<tbody>
{insider_rows}
</tbody>
</table>

<div class="footer">
Generated by Macro Sentinel | Data: FRED, CNN, OpenInsider, Yahoo Finance<br>
Note: Weekly/quarterly indicators show latest available data. Signals are algorithmic - use as reference alongside your own analysis.
</div>
</div>
</body>
</html>"""
    return html


# ============================================================
# Main Execution
# ============================================================

def main():
    print("=" * 60)
    print("MACRO SENTINEL - Collecting data...")
    print("=" * 60)

    date_str = datetime.date.today().strftime("%Y-%m-%d")
    indicators = {}

    # 1. FRED data
    print("[1/6] Fetching FRED data...")
    fred_data = fetch_all_fred()

    # 2. Analyze FRED-based indicators
    print("[2/6] Analyzing indicators...")

    if not fred_data["TGA"].empty:
        indicators["TGA"] = analyze_tga(fred_data["TGA"])
    else:
        indicators["TGA"] = {"signal": "NEUTRAL", "detail": "Data unavailable"}

    if not fred_data["WRESBAL"].empty:
        indicators["WRESBAL"] = analyze_wresbal(fred_data["WRESBAL"])
    else:
        indicators["WRESBAL"] = {"signal": "NEUTRAL", "detail": "Data unavailable"}

    if not fred_data["STLFSI4"].empty:
        indicators["STLFSI4"] = analyze_stlfsi(fred_data["STLFSI4"])
    else:
        indicators["STLFSI4"] = {"signal": "NEUTRAL", "detail": "Data unavailable"}

    if not fred_data["T10Y2Y"].empty:
        indicators["Yield Curve"] = analyze_yield_curve(fred_data["T10Y2Y"])
    else:
        indicators["Yield Curve"] = {"signal": "NEUTRAL", "detail": "Data unavailable"}

    sofr_data = fred_data["SOFR"]
    iorb_data = fred_data["IORB"]
    if sofr_data.empty or iorb_data.empty:
        sofr_data, iorb_data = fetch_sofr_iorb_direct()
    indicators["SOFR-IORB"] = analyze_sofr_iorb(sofr_data, iorb_data)
    indicators["RRP"] = analyze_rrp(fred_data["RRP"])
    indicators["DXY Quality"] = analyze_dxy_quality(fred_data["DXY"], fred_data.get("VIX", pd.Series(dtype=float)))

    # 3. ETF sector rotation
    print("[3/6] Fetching ETF data...")
    xlp = fetch_etf_prices("XLP")
    # Try LUXE, fallback to LVMUY (LVMH ADR) as luxury proxy
    luxury = fetch_etf_prices("LUXE")
    if luxury.empty:
        luxury = fetch_etf_prices("LVMUY")
    indicators["Sector Rotation"] = analyze_sector_rotation(xlp, luxury)

    # 4. Fear & Greed
    print("[4/6] Fetching Fear & Greed Index...")
    fg = fetch_fear_greed()
    indicators["Fear & Greed"] = analyze_fear_greed(fg)

    # 5. Insider trading
    print("[5/6] Fetching insider trading data...")
    insider = fetch_insider_trading()
    indicators["Insider Trading"] = analyze_insider_trading(insider)

    # 6. Primary Dealer positioning
    print("[6/6] Fetching Primary Dealer data...")
    pd_data = fetch_primary_dealer()
    indicators["Primary Dealer"] = analyze_primary_dealer(pd_data)

    # Generate report
    print("\nGenerating HTML report...")
    report_dir = Path(__file__).parent / REPORT_DIR
    report_dir.mkdir(exist_ok=True)
    html = generate_html(indicators, insider, fg, date_str)
    report_path = report_dir / f"macro_{date_str}.html"
    report_path.write_text(html, encoding="utf-8")
    print(f"\nReport saved: {report_path}")

    # Print summary to console
    print("\n" + "=" * 60)
    print(f"MACRO SENTINEL SUMMARY - {date_str}")
    print("=" * 60)
    for name, data in indicators.items():
        color_icon = {"BULLISH": "+", "BEARISH": "-", "CAUTION": "!", "NEUTRAL": "~"}
        icon = color_icon.get(data["signal"], "?")
        print(f"  [{icon}] {name:20s} {data['signal']:8s} | {data['detail']}")
    print("=" * 60)

    # Send Telegram notification
    print("\nSending Telegram notification...")
    try:
        from telegram_sender import send_telegram_message, format_macro_summary
        tg_text = format_macro_summary(indicators, fg, date_str)
        send_telegram_message(tg_text)
        print("Telegram message sent!")
    except Exception as e:
        print(f"[WARN] Telegram send failed: {e}")

    return str(report_path)


if __name__ == "__main__":
    report = main()
