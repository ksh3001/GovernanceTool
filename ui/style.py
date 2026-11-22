"""Shared look and feel.

The colours here never assume a light or a dark page. Borders and tints are derived from the
current text colour (`currentColor`) or use translucent accents, so the same CSS reads well
under both [theme.light] and [theme.dark] in .streamlit/config.toml.
"""
from __future__ import annotations

import streamlit as st

CSS = """
<style>
  :root { --pv-line: color-mix(in srgb, currentColor 16%, transparent);
          --pv-soft: color-mix(in srgb, currentColor 6%, transparent);
          --pv-accent: #6366F1; }

  /* page frame: leave room for Streamlit's own top bar, then our header bar */
  .block-container {padding-top: 4rem; padding-bottom: 1rem; max-width: 1180px;}
  h1, h2, h3 {letter-spacing: -0.02em;}
  [data-testid="stHeader"] {background: transparent;}

  /* header bar */
  .appbar {display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;
           padding:.55rem .9rem; margin-bottom:1rem; border:1px solid var(--pv-line); border-radius:12px;
           background: var(--pv-soft);}
  .crumbs {font-size:.88rem; opacity:.85;}
  .crumbs .sep {margin:0 .4rem; opacity:.5;}
  .crumbs .here {font-weight:700; opacity:1;}
  .pills {display:flex; gap:6px; flex-wrap:wrap;}
  .pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.74rem; font-weight:600;
         border:1px solid var(--pv-line);}

  /* footer */
  .appfooter {display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-top:3rem;
              padding-top:.8rem; border-top:1px solid var(--pv-line); font-size:.78rem; opacity:.7;}

  /* sidebar */
  .brand {font-size:1.35rem; font-weight:800; color: var(--pv-accent); letter-spacing:-0.02em;}
  .navlabel {font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; opacity:.6;
             margin:1rem 0 .3rem;}
  [data-testid="stSidebar"] .stButton > button {justify-content:flex-start; text-align:left; border-radius:10px;}
  [data-testid="stSidebar"] .stButton > button p {text-align:left;}
  .chip {display:inline-block; padding:1px 9px; border-radius:6px; background:rgba(99,102,241,.16);
         font-size:.72rem; font-weight:600; margin:0 4px 4px 0;}

  /* badges and notes */
  .tag {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:600; margin-right:6px;}
  .tag-draft {background:rgba(245,158,11,.22);}
  .tag-ok {background:rgba(34,197,94,.22);}
  .tag-soon {background:var(--pv-soft); border:1px solid var(--pv-line);}
  .muted {opacity:.7; font-size:.9rem;}
  .hint {background:rgba(99,102,241,.13); border-left:4px solid var(--pv-accent); padding:.55rem .8rem;
         border-radius:8px; font-size:.92rem; margin:.25rem 0 1rem;}

  /* citation viewer */
  .cv {font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:.82rem;
       border:1px solid var(--pv-line); border-radius:8px; overflow-x:auto; background:var(--pv-soft); margin:.25rem 0;}
  .cv .row {display:flex;}
  .cv .n {min-width:3rem; text-align:right; padding:0 .6rem; opacity:.55; background:var(--pv-soft); user-select:none;}
  .cv .t {white-space:pre; padding:0 .6rem; flex:1;}
  .cv .hit {background:rgba(34,197,94,.22);}
  .cv .claim {background:rgba(245,158,11,.28);}

  /* cards */
  .card {background: var(--pv-card); border:1px solid var(--pv-line); border-radius:16px; padding:1rem 1.1rem;
         box-shadow: var(--pv-shadow); margin-bottom:.9rem;}
  .card-title {font-weight:700; margin-bottom:.6rem;}
  [data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px;}
  .kpis {display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); gap:14px; margin:.4rem 0 1rem;}
  .kpis .card {margin-bottom:0;}
  .kpi-top {display:flex; justify-content:space-between; align-items:flex-start; gap:8px;}
  .kpi-label {font-size:.82rem; opacity:.7;}
  .kpi-value {font-size:2.1rem; font-weight:800; letter-spacing:-0.03em; line-height:1.15;}
  .kpi-sub {font-size:.78rem; opacity:.6; margin-top:.2rem;}
  .spark {flex:none; margin-top:.2rem;}
  .meter {height:8px; border-radius:999px; background:var(--pv-soft); overflow:hidden; border:1px solid var(--pv-line);}
  .meter .fill {height:100%; border-radius:999px;}
  .barrow {margin:.7rem 0;}
  .barhead {display:flex; justify-content:space-between; gap:8px; font-size:.86rem; margin-bottom:.3rem;}
  .barlabel {font-weight:600;}
  .barvalue {font-weight:700;}
  .barsub {font-size:.75rem; opacity:.6; margin-top:.25rem;}
  .tile {text-align:left;}
  .tile-art {font-size:1.6rem; width:46px; height:46px; display:flex; align-items:center; justify-content:center;
             border-radius:12px; background:linear-gradient(135deg, rgba(99,102,241,.25), rgba(236,72,153,.2)); margin-bottom:.6rem;}
  .tile-name {font-weight:700;}
  .promo {background:linear-gradient(135deg, #1E1B4B 0%, #4338CA 100%); color:#fff; border-radius:16px;
          padding:1.2rem 1.3rem; margin-bottom:.9rem; box-shadow: var(--pv-shadow);}
  .promo-pill {display:inline-block; padding:2px 10px; border-radius:999px; background:rgba(255,255,255,.18);
               font-size:.72rem; font-weight:700; margin-bottom:.6rem;}
  .promo-title {font-size:1.1rem; font-weight:800; margin-bottom:.35rem;}
  .promo-body {font-size:.86rem; opacity:.85;}
  .greet {font-size:1.9rem; font-weight:800; letter-spacing:-0.03em; line-height:1.2;}
  .greet-sub {opacity:.65; margin:.2rem 0 .6rem;}

  /* sidebar profile and progress card */
  .profile {display:flex; align-items:center; gap:10px; padding:.55rem .6rem; margin:.7rem 0 .2rem;
            border:1px solid var(--pv-line); border-radius:12px; background:var(--pv-soft);}
  .avatar {width:36px; height:36px; border-radius:50%; background:linear-gradient(135deg,#6366F1,#EC4899); color:#fff;
           display:flex; align-items:center; justify-content:center; font-weight:800;}
  .pname {font-weight:700; font-size:.9rem; line-height:1.1;}
  .prole {font-size:.72rem; opacity:.6;}
  .sidecard {padding:.7rem .8rem; border:1px solid var(--pv-line); border-radius:12px; background:var(--pv-soft);
             font-size:.78rem; margin-bottom:.6rem;}
  .sidecard .t {font-weight:700; margin-bottom:.4rem;}
  /* activity feed and insight */
  .feed {width:100%; border-collapse:collapse; font-size:.86rem;}
  .feed td {padding:.55rem .3rem; border-top:1px solid var(--pv-line); vertical-align:middle;}
  .feed tr:first-child td {border-top:none;}
  .feed .when {opacity:.6; white-space:nowrap;}
  .insight {background:rgba(34,197,94,.13); border:1px solid rgba(34,197,94,.35); border-radius:14px;
            padding:.8rem .95rem; margin-bottom:.9rem; font-size:.88rem;}
  .insight .t {font-weight:700; margin-bottom:.25rem;}
</style>
"""


LIGHT = "<style>:root{--pv-card:#FFFFFF; --pv-shadow:0 1px 3px rgba(15,23,42,.08);}</style>"
DARK = "<style>:root{--pv-card:#162033; --pv-shadow:0 1px 3px rgba(0,0,0,.4);}</style>"


def theme_type() -> str:
    """'light' or 'dark', as the browser reports the active Streamlit theme. Light if unknown."""
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        return "light"


def apply() -> None:
    st.markdown(CSS + (DARK if theme_type() == "dark" else LIGHT), unsafe_allow_html=True)
