"""Onboarding screen: application details and the questionnaire, with a live preview of the rules that apply."""
from __future__ import annotations

import streamlit as st

from core.config import ROOT, load_settings
from core.onboarding import onboard_application
from core.packs import discover_packs
from core.questionnaire import ANNEX_III_AREAS, PROHIBITED_PRACTICES, ROLE_LABELS, Questionnaire
from core.scope import preview
from core.store import Store
from ui import components as ui

AUTONOMY = {
    "fully_automated": "Fully automated: outcomes take effect without a person reviewing them",
    "human_reviews": "A person reviews outcomes before they take effect",
    "advisory_only": "Advisory only: output is information, a person decides",
}
TIER_COLOURS = {"prohibited": "#B91C1C", "high": "#C2410C", "limited": "#A16207",
                "minimal": "#15803D", "out_of_scope": "#475569"}


def _questionnaire() -> Questionnaire:
    """Read the answers from the widgets (all keyed ob_*), so the preview updates as the user answers."""
    s = st.session_state
    gpai = s.get("ob_gpai", False)
    return Questionnaire(
        purpose=s.get("ob_purpose", ""), role=s.get("ob_role", "provider"), eu_market=s.get("ob_eu", True),
        annex_iii_area=s.get("ob_area", "none"), safety_component_annex_i=s.get("ob_safety", False),
        affects_individuals=s.get("ob_affects", False), autonomy=s.get("ob_autonomy", "advisory_only"),
        narrow_procedural_task=s.get("ob_narrow", False), interacts_with_people=s.get("ob_interacts", False),
        generates_synthetic_content=s.get("ob_synthetic", False),
        emotion_or_biometric_categorisation=s.get("ob_emotion", False), deep_fake=s.get("ob_deepfake", False),
        public_body_or_service=s.get("ob_public", False), credit_or_insurance=s.get("ob_credit", False),
        gpai_model=gpai, gpai_systemic_risk=gpai and s.get("ob_systemic", False),
        prohibited_practices=[k for k in PROHIBITED_PRACTICES if s.get(f"pp_{k}", False)])


def _preview_card(q: Questionnaire, frameworks: list[str]) -> None:
    settings = load_settings()
    names = {p.id: p.name for p in discover_packs(settings.packs_dir)}
    st.markdown("##### Live preview")
    st.caption("Updates as you answer. Nothing is saved until you click Save.")
    for fw in frameworks:
        p = preview(q, settings.packs_dir / fw)
        with st.container(border=True):
            st.markdown(f"**{ui.E(names.get(fw, fw))}**")
            if p.tier:
                st.markdown(f'<span class="tag" style="background:{TIER_COLOURS.get(p.tier, "#475569")};color:#fff;'
                            f'font-size:.95rem;padding:3px 12px">{ui.E(p.tier_label)}</span> '
                            f'<span class="muted">{ui.E(p.legal_basis)}</span>', unsafe_allow_html=True)
                st.caption(p.reason)
            st.metric("Rules that apply", f"{len(p.rules)} of {p.total}")
            if p.rules:
                st.markdown("\n".join(f"- **{ui.E(a)}** · {ui.E(t)}" for a, t in p.rules))
            st.caption("You can still remove, add back or add custom rules in step 1 after saving.")


def render(store: Store) -> None:
    st.title("Onboard an application")
    st.caption("Tell us about the application. Your answers decide the risk tier and which rules it is assessed "
               "against.")
    frameworks = st.session_state.get("frameworks", [])
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("1. Application")
        name = st.text_input("Application name", key="ob_name")
        st.caption("Give the code either as a public repository URL or as a folder on this machine.")
        url = st.text_input("Repository URL", placeholder="https://github.com/owner/repo", key="ob_url",
                            help="Public repositories only. The code is fetched read-only and never run.")
        c1, c2 = st.columns(2)
        repo = c1.text_input("…or repository folder", key="ob_repo", help="Local path to the application's source code.")
        docs = c2.text_input("Documents folder (optional)", key="ob_docs",
                             help="Model cards, policies, data notes. Documents inside the repository are found automatically.")

        st.subheader("2. What it does")
        st.text_area("Intended purpose", key="ob_purpose",
                     placeholder="e.g. Ranks job applicants' CVs for recruiters.")
        st.radio("Your organisation's role", list(ROLE_LABELS), format_func=ROLE_LABELS.get, key="ob_role",
                 help="Providers and deployers have different duties under the Act.")
        st.checkbox("Placed on the market or used in the EU", value=True, key="ob_eu")
        st.selectbox("Does it operate in any of these areas?", list(ANNEX_III_AREAS), format_func=ANNEX_III_AREAS.get,
                     key="ob_area")
        st.checkbox("It is a safety component of a regulated product (machinery, medical device, vehicle, toys...)",
                    key="ob_safety")
        st.checkbox("Its output is used to make or support decisions about individual people", key="ob_affects")
        st.radio("Level of human involvement", list(AUTONOMY), format_func=AUTONOMY.get, key="ob_autonomy")
        st.checkbox("It only performs a narrow procedural or preparatory task, with no real influence on outcomes",
                    key="ob_narrow")

        st.subheader("3. Who uses it and for what")
        st.checkbox("It is used by a public body, or by a private organisation providing public services "
                    "(health, education, housing, benefits...)", key="ob_public")
        st.checkbox("It assesses people's creditworthiness or credit score, or prices life or health insurance",
                    key="ob_credit")

        st.subheader("4. Transparency")
        st.checkbox("People interact with it directly (chat, voice, ...)", key="ob_interacts")
        st.checkbox("It generates synthetic text, image, audio or video", key="ob_synthetic")
        st.checkbox("It recognises emotions or categorises people from biometric data (face, voice...)",
                    key="ob_emotion")
        st.checkbox("It generates or manipulates images, audio or video that could pass as real (deep fakes)",
                    key="ob_deepfake")

        st.subheader("5. General-purpose AI models")
        gpai = st.checkbox("We provide a general-purpose AI model (a foundation model) to others", key="ob_gpai")
        st.checkbox("The model has systemic risk (very high-capability, or designated by the Commission)",
                    key="ob_systemic", disabled=not gpai)

        st.subheader("6. Prohibited practices screen")
        st.caption("Tick anything that applies. This should normally be empty.")
        for k, label in PROHIBITED_PRACTICES.items():
            st.checkbox(label, key=f"pp_{k}")

    q = _questionnaire()
    with right:
        _preview_card(q, frameworks)

    with left:
        st.write("")
        b1, b2 = st.columns([1, 1])
        submitted = b1.button("Save application", type="primary", key="ob_save")
        cancel = b2.button("Cancel", key="ob_cancel")
    if cancel:
        _clear()
        st.session_state.page = "home"
        st.rerun()
    if submitted:
        try:
            with st.spinner("Fetching repository…" if url.strip() else "Saving…"):
                record = onboard_application(store, name=name, repo_path=repo, repo_url=url, docs_path=docs,
                                             questionnaire=q, frameworks=frameworks, user=st.session_state.user,
                                             samples_dir=ROOT / "samples")
        except ValueError as exc:  # includes FetchError
            with left:
                for line in str(exc).splitlines():
                    st.error(line)
            return
        _clear()
        st.session_state.flash = f"Saved '{record.name}'. Next: confirm its rule scope."
        st.session_state.page = "app"
        st.session_state.app_id = record.app_id
        st.rerun()


def _clear() -> None:
    for k in [k for k in st.session_state if str(k).startswith(("ob_", "pp_"))]:
        del st.session_state[k]
