"""Small HTML building blocks for cards, KPI tiles and bars. Every value is escaped."""
from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st

from core.findings import STATUS_LABELS
from ui.findings import STATUS_COLOURS

E = html.escape


def greeting(name: str, now: datetime | None = None) -> str:
    hour = (now or datetime.now()).hour
    part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    return f"Good {part}, {name}"


def pct_text(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def spark(values: list[float], colour: str = "#6366F1") -> str:
    """A tiny bar chart as inline SVG."""
    if not values or max(values) <= 0:
        return ""
    top = max(values)
    w, gap, h = 7, 3, 34
    bars = "".join(
        f'<rect x="{i * (w + gap)}" y="{h - max(3, v / top * h):.1f}" width="{w}" height="{max(3, v / top * h):.1f}" '
        f'rx="2" fill="{colour}" opacity="{0.45 + 0.55 * v / top:.2f}"/>' for i, v in enumerate(values))
    return f'<svg class="spark" width="{len(values) * (w + gap)}" height="{h}" aria-hidden="true">{bars}</svg>'


def kpi(label: str, value: str, sub: str = "", visual: str = "") -> str:
    return (f'<div class="card kpi"><div class="kpi-top"><div><div class="kpi-label">{E(label)}</div>'
            f'<div class="kpi-value">{E(value)}</div></div>{visual}</div>'
            f'<div class="kpi-sub">{E(sub)}</div></div>')


def kpis(*cards: str) -> None:
    st.markdown(f'<div class="kpis">{"".join(cards)}</div>', unsafe_allow_html=True)


def meter(pct: float, colour: str = "#6366F1") -> str:
    pct = max(0.0, min(100.0, pct))
    return f'<div class="meter"><div class="fill" style="width:{pct:.0f}%;background:{colour}"></div></div>'


def bar_row(label: str, value: str, pct: float, colour: str = "#6366F1", sub: str = "") -> str:
    return (f'<div class="barrow"><div class="barhead"><span class="barlabel">{E(label)}</span>'
            f'<span class="barvalue">{E(value)}</span></div>{meter(pct, colour)}'
            + (f'<div class="barsub">{E(sub)}</div>' if sub else "") + '</div>')


def card(title: str, body: str, note: str = "") -> None:
    st.markdown(f'<div class="card"><div class="card-title">{E(title)}</div>{body}'
                + (f'<div class="barsub">{E(note)}</div>' if note else "") + '</div>', unsafe_allow_html=True)


def promo(title: str, body: str, pill: str = "") -> None:
    st.markdown(f'<div class="promo">' + (f'<span class="promo-pill">{E(pill)}</span>' if pill else "") +
                f'<div class="promo-title">{E(title)}</div><div class="promo-body">{E(body)}</div></div>',
                unsafe_allow_html=True)


def tile(name: str, desc: str, tag: str, tag_class: str) -> str:
    return (f'<div class="card tile"><div class="tile-art">🛡️</div><div class="tile-name">{E(name)}</div>'
            f'<div class="barsub">{E(desc)}</div><span class="tag {tag_class}">{E(tag)}</span></div>')


def profile(name: str, role: str = "Reviewer") -> str:
    initial = (name.strip()[:1] or "?").upper()
    return (f'<div class="profile"><div class="avatar">{E(initial)}</div>'
            f'<div><div class="pname">{E(name)}</div><div class="prole">{E(role)}</div></div></div>')


def status_bars(counts: dict[str, int]) -> list[tuple[str, int, str]]:
    return [(STATUS_LABELS[s], counts.get(s, 0), STATUS_COLOURS[s]) for s in STATUS_LABELS]


def ago(iso: str, now: datetime | None = None) -> str:
    """'5 min ago', '2 h ago', '3 d ago' for an ISO timestamp."""
    try:
        then = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    secs = max(0, int(((now or datetime.now(timezone.utc)) - then).total_seconds()))
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60} min ago"
    if secs < 86400:
        return f"{secs // 3600} h ago"
    return f"{secs // 86400} d ago"


def activity_table(items) -> str:
    if not items:
        return '<div class="barsub">Nothing yet. Run an assessment to start the activity feed.</div>'
    rows = []
    for a in items:
        if a.status == "completed":
            pill = '<span class="tag tag-ok">Completed</span>'
        else:
            pill = f'<span class="tag" style="background:{STATUS_COLOURS.get(a.status, "#475569")};color:#fff">{E(STATUS_LABELS.get(a.status, a.status))}</span>'
        rows.append(f'<tr><td><b>{E(a.title)}</b><div class="barsub">{E(a.detail)}</div></td><td>{E(a.app)}</td>'
                    f'<td class="when">{E(ago(a.at))}</td><td>{pill}</td></tr>')
    return '<table class="feed">' + "".join(rows) + "</table>"


# ---- governance workflow building blocks -------------------------------------------------------

def stepper(steps: list[tuple[str, str]], current: str) -> str:
    """Horizontal workflow tracker. `steps` is [(name, state)] with state done|todo|locked; `current` is the open step."""
    items = []
    for i, (name, state) in enumerate(steps, 1):
        cls = "current" if name == current else state
        mark = "✓" if state == "done" and name != current else str(i)
        items.append(f'<div class="step {cls}"><span class="dot">{mark}</span><span class="lbl">{E(name)}</span></div>')
    return f'<div class="stepper" role="list">{"".join(items)}</div>'


def page_title(title: str, subtitle: str = "", chips: list[str] | None = None) -> None:
    st.markdown(f'<div class="ptitle"><h1>{E(title)}</h1>' + (f'<div class="psub">{subtitle}</div>' if subtitle else "")
                + (f'<div class="pchips">{"".join(chips)}</div>' if chips else "") + '</div>', unsafe_allow_html=True)


def chip(text: str, colour: str | None = None) -> str:
    style = f' style="background:{colour};color:#fff;border-color:transparent"' if colour else ""
    return f'<span class="pill"{style}>{E(text)}</span>'


def stacked_bar(counts: dict[str, int]) -> str:
    """One bar split by finding status, with a legend. Shows the whole posture at a glance."""
    total = sum(counts.values())
    if not total:
        return ""
    segs = "".join(f'<span class="seg" title="{E(label)}: {n}" style="width:{100 * n / total:.2f}%;background:{colour}"></span>'
                   for label, n, colour in status_bars(counts) if n)
    legend = "".join(f'<span class="lg"><i style="background:{colour}"></i>{E(label)} <b>{n}</b></span>'
                     for label, n, colour in status_bars(counts) if n)
    return f'<div class="stack">{segs}</div><div class="legend">{legend}</div>'


def verdict_banner(headline: str, detail: str, tone: str = "info") -> None:
    """A large headline for the state of an assessment. tone: good | warn | bad | info."""
    st.markdown(f'<div class="verdict {tone}"><div class="vh">{E(headline)}</div><div class="vd">{E(detail)}</div></div>',
                unsafe_allow_html=True)


def empty_state(icon: str, title: str, body: str) -> None:
    st.markdown(f'<div class="empty"><div class="ei">{E(icon)}</div><div class="et">{E(title)}</div>'
                f'<div class="eb">{E(body)}</div></div>', unsafe_allow_html=True)
