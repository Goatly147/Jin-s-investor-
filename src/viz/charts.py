"""Plotly 차트 팩토리 — 이벤트 오버레이 / 듀얼축 / 섹터 바."""

from datetime import date
from typing import Iterable, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


COLOR_PRIMARY = "#E63946"
COLOR_SECONDARY = "#457B9D"
COLOR_POSITIVE = "#2A9D8F"
COLOR_NEGATIVE = "#E63946"
COLOR_NEUTRAL = "#A8A8A8"


def _vline_at_date(fig: go.Figure, d, color: str, width: float, dash: str,
                   opacity: float = 1.0, label: Optional[str] = None) -> None:
    """add_shape + add_annotation 분리 — Plotly 6.x + pandas 3.x에서 add_vline 결합 버그 회피."""
    ts = pd.Timestamp(d)
    fig.add_shape(
        type="line", xref="x", yref="paper",
        x0=ts, x1=ts, y0=0, y1=1,
        line=dict(color=color, width=width, dash=dash),
        opacity=opacity,
    )
    if label:
        fig.add_annotation(
            x=ts, y=1, xref="x", yref="paper",
            text=label, showarrow=False,
            xanchor="left", yanchor="bottom",
            font=dict(color=color, size=11),
        )


def _add_event_lines(fig: go.Figure, anchor: Optional[date], escalations: Iterable[date]) -> None:
    if anchor is not None:
        _vline_at_date(fig, anchor, COLOR_PRIMARY, 2, "dash", label="발발일")
    for d in escalations or []:
        _vline_at_date(fig, d, "#F4A261", 1, "dot", opacity=0.6)


def price_with_events(
    price: pd.Series,
    vix: Optional[pd.Series] = None,
    anchor: Optional[date] = None,
    escalations: Optional[Iterable[date]] = None,
    title: str = "S&P 500 + VIX",
) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=price.index, y=price.values, name="S&P 500", line=dict(color=COLOR_SECONDARY, width=2)),
        secondary_y=False,
    )
    if vix is not None and not vix.empty:
        fig.add_trace(
            go.Scatter(x=vix.index, y=vix.values, name="VIX", line=dict(color=COLOR_PRIMARY, width=1.4), opacity=0.85),
            secondary_y=True,
        )
    _add_event_lines(fig, anchor, escalations or [])
    fig.update_layout(
        title=title,
        height=480,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=1.08),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="S&P 500", secondary_y=False)
    fig.update_yaxes(title_text="VIX", secondary_y=True, showgrid=False)
    return fig


def returns_lines(
    returns_df: pd.DataFrame,
    anchor: Optional[date] = None,
    escalations: Optional[Iterable[date]] = None,
    title: str = "발발일 이후 수익률 (%)",
) -> go.Figure:
    fig = go.Figure()
    for col in returns_df.columns:
        fig.add_trace(
            go.Scatter(
                x=returns_df.index,
                y=returns_df[col].values,
                name=col,
                mode="lines",
                line=dict(width=1.6),
            )
        )
    _add_event_lines(fig, anchor, escalations or [])
    fig.add_hline(y=0, line=dict(color=COLOR_NEUTRAL, width=1, dash="dot"))
    fig.update_layout(
        title=title,
        height=480,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=-0.18),
        hovermode="x unified",
        yaxis_ticksuffix="%",
    )
    return fig


def sector_bar(snap: pd.DataFrame, value_col: str = "수익률(%)", label_col: str = "섹터") -> go.Figure:
    df = snap.sort_values(value_col)
    colors = [COLOR_POSITIVE if v >= 0 else COLOR_NEGATIVE for v in df[value_col]]
    fig = go.Figure(
        go.Bar(
            x=df[value_col].values,
            y=df[label_col].values,
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.2f}%" for v in df[value_col]],
            textposition="outside",
        )
    )
    fig.add_vline(x=0, line=dict(color=COLOR_NEUTRAL, width=1))
    fig.update_layout(
        title="섹터별 발발일 이후 수익률",
        height=480,
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis_ticksuffix="%",
    )
    return fig


def gauge(value: float, title: str, vmin: float = 0, vmax: float = 100, suffix: str = "") -> go.Figure:
    bar_color = COLOR_PRIMARY if value < (vmin + vmax) / 2 else COLOR_POSITIVE
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": suffix, "valueformat": ".1f"},
            title={"text": title, "font": {"size": 14}},
            gauge={
                "axis": {"range": [vmin, vmax]},
                "bar": {"color": bar_color},
                "steps": [
                    {"range": [vmin, (vmin + vmax) * 0.25], "color": "#264653"},
                    {"range": [(vmin + vmax) * 0.25, (vmin + vmax) * 0.75], "color": "#1d3557"},
                    {"range": [(vmin + vmax) * 0.75, vmax], "color": "#264653"},
                ],
            },
        )
    )
    fig.update_layout(height=240, margin=dict(l=20, r=20, t=40, b=20))
    return fig


def small_multiples(series_dict: dict, title: str = "") -> go.Figure:
    items = list(series_dict.items())
    rows, cols = 2, 2
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=[k for k, _ in items[: rows * cols]],
        vertical_spacing=0.14,
        horizontal_spacing=0.08,
    )
    for i, (name, s) in enumerate(items[: rows * cols]):
        r, c = i // cols + 1, i % cols + 1
        if s is None or len(s) == 0:
            continue
        fig.add_trace(
            go.Scatter(x=s.index, y=s.values, name=name, mode="lines",
                       line=dict(color=COLOR_SECONDARY, width=1.6), showlegend=False),
            row=r, col=c,
        )
    fig.update_layout(
        title=title,
        height=560,
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig
