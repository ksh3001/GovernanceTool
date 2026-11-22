"""Overview page: greeting, KPI cards, application cards, common gaps, frameworks and run mode."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from core.config import ROOT, Settings
from core.models import AppRecord
from core.onboarding import load_questionnaire
from core.overview import AppRow, Overview
from core.packs import discover_packs
from core.samples import install_samples
from core.store import Store
from core.tiers import load_classifier
from ui import components as ui
from ui.findings import STATUS_COLOURS
from ui.nav import header
from ui.style import theme_type

TIER_STYLE = {"prohibited": "#B91C1C", "high": "#C2410C", "limited": "#A16207",
              "minimal": "#15803D", "out_of_scope": "#475569"}

MODE_TEXT = {
    "fake": ("Placeholder results", "The model is not called. Findings are fixed placeholders so you can click through the whole flow."),
    "replay": ("Replay mode", "Answers come from a saved recording of a real run, so the demo works without internet or Azure."),
    "live": ("Live model", "Each assessment calls the Azure OpenAI deployment. Check the run summary for the token estimate first."),
}


def _tier_reason(settings: Settings, app: AppRecord, store: Store) -> None:
    q = load_questionnaire(store, app.app_id)
    for fw in app.frameworks:
        classify = load_classifier(settings.packs_dir / fw)
        if q is None or classify is None:
            continue
        result = classify(q)
        with st.expander("Why this tier?"):
            st.write(result.reason)
            for step in result.steps:
                st.markdown(f"{'✅' if step.matched else '▫️'} {step.question}" + (f" — _{step.detail}_" if step.detail else ""))
            st.caption(f"Rule `{result.rule_id}` · [Regulation (EU) 2024/1689]({result.source_url})")


def _app_card(settings: Settings, store: Store, app: AppRecord, row: AppRow) -> None:
    with st.container(border=True):
        head, action = st.columns([4, 1])
        head.subheader(row.name)
        pills = []
        if row.tier_label:
            colour = TIER_STYLE.get(row.tier, "#475569")
            pills.append(f'<span class="tag" style="background:{colour};color:#fff">{ui.E(row.tier_label)}</span>')
        if row.assessed:
            pills.append(f'<span class="tag tag-ok">Assessed · score {ui.pct_text(row.score)}</span>')
            if row.placeholder:
                pills.append('<span class="tag tag-draft">Placeholder results</span>')
        else:
            pills.append('<span class="tag tag-soon">Not assessed yet</span>')
        head.markdown("".join(pills), unsafe_allow_html=True)
        if row.purpose:
            head.markdown(f'<p class="muted">{ui.E(row.purpose)}</p>', unsafe_allow_html=True)
        if row.assessed:
            head.markdown(ui.bar_row(f"{row.reviewed} of {row.total} findings reviewed", ui.pct_text(row.score),
                                     100 * row.reviewed / max(row.total, 1), "#6366F1"), unsafe_allow_html=True)
        head.caption("Repository: " + row.repo)
        if action.button("Open application", key=f"open_{row.app_id}", type="primary", width="stretch"):
            st.session_state.page = "app"
            st.session_state.app_id = row.app_id
            st.rerun()
        _tier_reason(settings, app, store)


def _open_step(app_id: str, framework: str, section: str) -> None:
    """Button callback: jump straight to a step of an application."""
    st.session_state.page = "app"
    st.session_state.app_id = app_id
    st.session_state.goto_section = (framework, section)


def _donut(counts: dict[str, int]) -> None:
    total = sum(counts.values())
    if not total:
        st.markdown('<div class="barsub">No findings yet. Run an assessment to see the split.</div>', unsafe_allow_html=True)
        return
    rows = [{"Status": label, "Findings": n} for label, n, _ in ui.status_bars(counts) if n]
    colours = {label: colour for label, _, colour in ui.status_bars(counts)}
    base = alt.Chart(pd.DataFrame(rows)).encode(
        theta=alt.Theta("Findings:Q", stack=True),
        color=alt.Color("Status:N", scale=alt.Scale(domain=list(colours), range=list(colours.values())),
                        legend=alt.Legend(orient="right", title=None)),
        tooltip=["Status", "Findings"])
    text_colour = "#E5E7EB" if theme_type() == "dark" else "#0F172A"
    centre = alt.Chart(pd.DataFrame({"t": [str(total)]})).mark_text(size=30, fontWeight="bold", color=text_colour).encode(text="t:N")
    st.altair_chart(base.mark_arc(innerRadius=58, outerRadius=88, cornerRadius=4) + centre, width="stretch")
    st.caption("Total findings across all applications")


def render(store: Store, settings: Settings, overview: Overview, apps: list[AppRecord]) -> None:
    header("Overview", mode=settings.llm_mode)
    if flash := st.session_state.pop("flash", None):
        st.success(flash)

    search, a, b = st.columns([3, 1.2, 1.4], vertical_alignment="center")
    query = search.text_input("Search applications", placeholder="🔍  Search applications…", key="app_search",
                              label_visibility="collapsed").strip().lower()
    if a.button("Load sample apps", width="stretch", help="Adds the HR CV Screener and Support Chatbot demo applications."):
        added = install_samples(store, ROOT / "samples", st.session_state.frameworks, st.session_state.user)
        st.session_state.flash = f"Loaded {len(added)} sample app(s)." if added else "Sample apps are already loaded."
        st.rerun()
    if b.button("＋  Onboard an application", type="primary", width="stretch"):
        st.session_state.page = "onboard"
        st.rerun()

    st.markdown(f'<div class="greet">{ui.E(ui.greeting(st.session_state.user))} 👋</div>'
                '<div class="greet-sub">Here is what is happening with your AI applications. '
                'Assess each one, review every finding and download the report.</div>', unsafe_allow_html=True)

    counts = overview.status_counts
    scores = [r.score for r in overview.rows if r.score is not None]
    ui.kpis(
        ui.kpi("Applications", str(len(overview.rows)), f"{overview.assessed_apps} assessed",
               ui.spark([1.0] * len(overview.rows)) if overview.rows else ""),
        ui.kpi("Average compliance score", ui.pct_text(overview.avg_score), "Internal metric, not an official EU rating",
               ui.spark(scores, "#22C55E")),
        ui.kpi("Findings reviewed", f"{overview.reviewed} / {overview.total}", "Confirmed or overridden by a person",
               ui.spark([overview.reviewed, max(overview.total - overview.reviewed, 0)], "#6366F1")),
        ui.kpi("Open gaps", str(overview.gap_total), "Not met or insufficient evidence",
               ui.spark([counts["not_met"], counts["insufficient_evidence"]], "#B91C1C")))

    main, rail = st.columns([3.2, 1.5])
    with main:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Findings by status")
            _donut(counts)
        with c2:
            assessed = [r for r in overview.rows if r.score is not None]
            body = ("".join(ui.bar_row(r.name, ui.pct_text(r.score), 100 * (r.score or 0), "#22C55E") for r in assessed)
                    if assessed else '<div class="barsub">No scores yet.</div>')
            ui.card("Compliance score by application", body, "Reviewer decisions are included")
            if overview.top_gaps:
                top = max(g.apps for g in overview.top_gaps)
                ui.card("Most common gaps", "".join(
                    ui.bar_row(f"{g.article} · {g.title}", f"{g.apps} app{'s' if g.apps != 1 else ''}", 100 * g.apps / top, "#B91C1C")
                    for g in overview.top_gaps))

        st.markdown("#### Applications")
        shown = [x for x in apps if query in x.name.lower() or query in (next((r.purpose for r in overview.rows if r.app_id == x.app_id), "")).lower()]
        if not apps:
            st.info("No applications yet. Use **Load sample apps** for a ready-made demo, or **Onboard an application** to add your own.")
        elif not shown:
            st.info(f"No application matches “{query}”.")
        rows = {r.app_id: r for r in overview.rows}
        for app in shown:
            _app_card(settings, store, app, rows[app.app_id])

        st.markdown("#### Recent activity")
        ui.card("Assessments and review decisions", ui.activity_table(overview.activity))

    with rail:
        st.markdown("##### Next steps")
        if not overview.next_actions:
            st.caption("Load the sample apps or onboard your own to get started.")
        for n in overview.next_actions:
            st.button(f"{ {'Run': '▶️', 'Review': '🔍', 'Report': '📄'}[n.section] }  {n.text}", key=f"next_{n.app_id}",
                      width="stretch", on_click=_open_step, args=(n.app_id, n.framework, n.section))
        if overview.top_gaps:
            g = overview.top_gaps[0]
            st.markdown(f'<div class="insight"><div class="t">💡 Insight</div>{ui.E(g.article)} · {ui.E(g.title)} is the most '
                        'common gap. Open an application’s Dashboard to see the proposed solution for each gap.</div>',
                        unsafe_allow_html=True)
        title, body = MODE_TEXT.get(settings.llm_mode, (settings.llm_mode, ""))
        ui.promo(title, body, pill=f"LLM mode: {settings.llm_mode}")
        st.markdown("##### Frameworks")
        for pack in discover_packs(settings.packs_dir):
            if not pack.available:
                st.markdown(ui.tile(pack.name, pack.description, "Coming soon", "tag-soon"), unsafe_allow_html=True)
            elif pack.status == "reviewed":
                st.markdown(ui.tile(pack.name, pack.description, "Expert reviewed", "tag-ok"), unsafe_allow_html=True)
            else:
                st.markdown(ui.tile(pack.name, pack.description, "Draft, pending expert review", "tag-draft"), unsafe_allow_html=True)
