"""스타일된 dataframe 헬퍼."""

import pandas as pd


def style_sector_table(df: pd.DataFrame):
    fmt = {
        "수익률(%)": "{:+.2f}",
        "현재 PER": "{:.1f}",
        "현재 EPS": "{:.2f}",
        "현재가": "{:.2f}",
    }
    fmt = {k: v for k, v in fmt.items() if k in df.columns}

    def color_returns(val):
        if pd.isna(val):
            return ""
        if val > 0:
            return "color: #2A9D8F; font-weight: 600;"
        if val < 0:
            return "color: #E63946; font-weight: 600;"
        return ""

    styler = df.style.format(fmt, na_rep="—")
    if "수익률(%)" in df.columns:
        styler = styler.map(color_returns, subset=["수익률(%)"])
    return styler
