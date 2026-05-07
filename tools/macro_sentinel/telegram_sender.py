"""
Telegram notification helpers for Macro Sentinel.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from the environment.
In GitHub Actions, set them as repository Secrets and inject via the
workflow's `env:` block.
"""
import os

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SIGNAL_MARK = {
    "BULLISH": "[+]",
    "BEARISH": "[-]",
    "CAUTION": "[!]",
    "NEUTRAL": "[~]",
}


def send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=20,
    )
    resp.raise_for_status()


def _decide_overall(counts: dict) -> str:
    total = sum(counts.values()) or 1
    bull_pct = counts.get("BULLISH", 0) / total * 100
    bear_pct = counts.get("BEARISH", 0) / total * 100
    if bull_pct > 50:
        return "BULLISH"
    if bear_pct > 40:
        return "BEARISH"
    if counts.get("CAUTION", 0) >= 3:
        return "CAUTION"
    return "NEUTRAL"


def format_macro_summary(indicators: dict, fear_greed: dict, date_str: str) -> str:
    counts = {"BULLISH": 0, "BEARISH": 0, "CAUTION": 0, "NEUTRAL": 0}
    for ind in indicators.values():
        sig = ind.get("signal", "NEUTRAL")
        counts[sig] = counts.get(sig, 0) + 1

    overall = _decide_overall(counts)
    lines = [
        f"<b>Macro Sentinel - {date_str}</b>",
        f"Overall: <b>{overall}</b>",
        f"Bull {counts['BULLISH']} | Caution {counts['CAUTION']} | Bear {counts['BEARISH']} | Neutral {counts['NEUTRAL']}",
        "",
    ]
    for name, data in indicators.items():
        mark = SIGNAL_MARK.get(data.get("signal", "NEUTRAL"), "[?]")
        detail = str(data.get("detail", ""))
        if len(detail) > 160:
            detail = detail[:157] + "..."
        lines.append(f"{mark} <b>{name}</b>: {detail}")

    score = fear_greed.get("score") if fear_greed else None
    if score is not None:
        rating = fear_greed.get("rating", "")
        lines.append("")
        lines.append(f"Fear &amp; Greed: <b>{score}</b> ({rating})")

    return "\n".join(lines)
