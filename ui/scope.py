"""Rule scope step: see which rules the questionnaire selected and why, adjust them, then finalise."""
from __future__ import annotations

import streamlit as st

from core.controls import Control
from core.questionnaire import ANNEX_III_AREAS, ROLE_LABELS, Questionnaire
from core.scope import (ScopeFile, ScopedRule, add_custom_rule, exclude_rule, finalise, include_rule,
                        remove_custom_rule, reopen, revert_rule, scope_path, scoped_rules, summarise_scope)
from core.store import Store
from core.tiers import Applicability, TierResult, flag_text
from ui import components as ui

TIER_COLOURS = {"prohibited": "#B91C1C", "high": "#C2410C", "limited": "#A16207",
                "minimal": "#15803D", "out_of_scope": "#475569"}
CHANGE_TAG = {"added": ("Added by reviewer", "tag-draft"), "removed": ("Removed by reviewer", "tag-draft"),
              "custom": ("Custom rule", "tag-ok")}
EVIDENCE = {"code": "Code", "document": "Documents", "both": "Code and documents"}
FLAGS = ("interacts_with_people", "generates_synthetic_content", "emotion_or_biometric_categorisation", "deep_fake",
         "public_body_or_service", "credit_or_insurance", "gpai_model", "gpai_systemic_risk")


def _save(store: Store, scope: ScopeFile) -> None:
    store.save(scope.app_id, scope_path(scope.framework), scope)


def _answers(q: Questionnaire, tier: TierResult | None) -> None:
    """The questionnaire answers that drove the scope, in plain words."""
    lines = [f"**Role:** {ROLE_LABELS[q.role]}",
             f"**Area:** {ANNEX_III_AREAS.get(q.annex_iii_area, q.annex_iii_area)}",
             f"**Human involvement:** {q.autonomy.replace('_', ' ')}"]
    on = [flag_text(f) for f in FLAGS if getattr(q, f, False)]
    lines.append("**It also:** " + ("; ".join(on) if on else "none of the transparency or special cases"))
    if tier:
        lines.append(f"**Risk tier:** {tier.label} · {tier.legal_basis}")
    st.markdown("  \n".join(lines))


def _rule_row(store: Store, scope: ScopeFile, r: ScopedRule, user: str) -> None:
    c: Control = r.control
    with st.container(border=True):
        left, right = st.columns([5, 1.4], vertical_alignment="center")
        tags = ""
        if r.change:
            label, cls = CHANGE_TAG[r.change]
            tags = f' <span class="tag {cls}">{label}</span>'
        left.markdown(f"**{ui.E(c.article)}** · {ui.E(c.title)}{tags}", unsafe_allow_html=True)
        left.caption(f"{r.reason}  ·  Evidence: {EVIDENCE[c.expected_evidence]}")
        with left.expander("What the rule requires"):
            st.write(" ".join(c.paraphrase.split()))
            if c.quote:
                st.caption(f"“{c.quote}” · [source]({c.source_url})" if c.source_url else f"“{c.quote}”")
        if scope.finalised:
            return
        key = f"{scope.framework}_{c.id}"
        with right:
            if r.change == "custom":
                if st.button("Remove", key=f"scope_delcustom_{key}"):
                    remove_custom_rule(scope, c.id, user)
                    _save(store, scope)
                    st.rerun()
            elif r.change:
                if st.button("Undo", key=f"scope_undo_{key}", help="Go back to what the questionnaire proposed."):
                    revert_rule(scope, c.id, user)
                    _save(store, scope)
                    st.rerun()
            else:
                label = "Remove" if r.applies else "Add to scope"
                with st.popover(label):
                    with st.form(f"scope_form_{key}", border=False):
                        reason = st.text_area("Reason (kept in the audit trail and shown in the report)",
                                              key=f"scope_reason_{key}",
                                              placeholder=("e.g. Covered centrally by the group compliance team"
                                                           if r.applies else "e.g. The bank's policy requires it anyway"))
                        ok = st.form_submit_button("Remove rule" if r.applies else "Add rule", type="primary")
                    if ok:
                        try:
                            (exclude_rule if r.applies else include_rule)(scope, c.id, reason, user)
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            _save(store, scope)
                            st.rerun()


def _custom_form(store: Store, scope: ScopeFile, user: str) -> None:
    with st.expander("➕  Add a custom rule", expanded=False):
        st.caption("For an obligation the pack does not cover, such as an internal AI policy, a client requirement "
                   "or a specific paragraph you want checked on its own. It is assessed like any other rule.")
        with st.form(f"scope_custom_{scope.framework}"):
            c1, c2 = st.columns([1, 2])
            reference = c1.text_input("Reference", placeholder="e.g. EY AI Policy §4.2")
            title = c2.text_input("Title", placeholder="e.g. Prompt and response logging")
            requirement = st.text_area("Requirement: what must be true",
                                       placeholder="e.g. Every prompt sent to the model and every response is stored "
                                                   "with a timestamp and user id for 12 months.")
            c3, c4 = st.columns([1, 2])
            evidence = c3.selectbox("Evidence expected in", list(EVIDENCE), index=2, format_func=EVIDENCE.get)
            terms = c4.text_input("Keywords (optional, comma separated)",
                                  help="Used to find the relevant files. If empty, keywords are taken from the title "
                                       "and requirement.")
            remediation = st.text_area("Proposed solution if not met (optional, one step per line)")
            reason = st.text_input("Why it is added (optional)")
            ok = st.form_submit_button("Add custom rule", type="primary")
        if ok:
            try:
                add_custom_rule(scope, reference=reference, title=title, requirement=requirement,
                                expected_evidence=evidence, search_terms=terms, remediation=remediation,
                                reason=reason, by=user)
            except ValueError as exc:
                for line in str(exc).splitlines():
                    st.error(line)
            else:
                _save(store, scope)
                st.rerun()


def render(store: Store, app_id: str, framework: str, q: Questionnaire, tier: TierResult | None,
           controls: list[Control], applicability: list[Applicability], scope: ScopeFile) -> None:
    user = st.session_state.user
    rules = scoped_rules(controls, applicability, scope)
    s = summarise_scope(rules)

    if scope.finalised:
        st.success(f"Scope finalised by {scope.finalised_by} on {scope.finalised_at}. "
                   f"{s.in_scope} rules will be assessed.")
    else:
        st.info("The questionnaire has proposed the rules below. Remove any that do not apply in practice, add back "
                "any you want checked, or add your own. Then finalise the scope to run the assessment.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.caption("Risk tier")
        if tier:
            st.markdown(f'<span class="tag" style="background:{TIER_COLOURS.get(tier.tier, "#475569")};color:#fff;'
                        f'font-size:1rem;padding:4px 14px">{ui.E(tier.label)}</span>', unsafe_allow_html=True)
            st.caption(tier.legal_basis)
    c2.metric("Rules in scope", s.in_scope, delta=f"{s.proposed} proposed by the questionnaire", delta_color="off")
    c3.metric("Not applicable", s.out_of_scope, help="Ruled out by the risk tier, your role or your answers.")
    c4.metric("Changed by reviewer", s.removed + s.added + s.custom,
              delta=f"{s.removed} removed · {s.added} added · {s.custom} custom", delta_color="off")

    with st.expander("Why these rules? The answers that drove the scope"):
        _answers(q, tier)
        if tier:
            st.caption(tier.reason)

    st.subheader(f"In scope ({s.in_scope})")
    for r in rules:
        if r.applies:
            _rule_row(store, scope, r, user)
    if not scope.finalised:
        _custom_form(store, scope, user)

    st.subheader(f"Not applicable ({s.out_of_scope})")
    if not s.out_of_scope:
        st.caption("Every rule in the pack applies.")
    elif st.toggle("Show each rule that was ruled out, and why", key=f"scope_show_na_{framework}",
                   value=s.added > 0 or s.removed > 0):
        for r in rules:
            if not r.applies:
                _rule_row(store, scope, r, user)

    st.write("")
    if scope.finalised:
        b1, b2 = st.columns([1, 3])
        if b1.button("Go to step 2 · Run", type="primary", key=f"scope_next_{framework}"):
            st.session_state.goto_section = (framework, "Run")
            st.rerun()
        if b2.button("Reopen scope to make changes", key=f"scope_reopen_{framework}"):
            reopen(scope, user)
            _save(store, scope)
            st.rerun()
    elif st.button(f"Finalise scope · {s.in_scope} rules", type="primary", key=f"scope_finalise_{framework}",
                   disabled=s.in_scope == 0):
        try:
            finalise(scope, rules, user)
        except ValueError as exc:
            st.error(str(exc))
        else:
            _save(store, scope)
            st.session_state.goto_section = (framework, "Run")
            st.rerun()

    if scope.history:
        with st.expander(f"Scope audit trail ({len(scope.history)})"):
            for e in reversed(scope.history):
                st.markdown(f"`{e.at}` · **{ui.E(e.by)}** {e.action.replace('_', ' ')} "
                            f"{ui.E(e.control_id)}" + (f" — {ui.E(e.detail)}" if e.detail else ""))
