"""Onboarding screen: application details plus the risk questionnaire."""
from __future__ import annotations

import streamlit as st

from core.config import ROOT
from core.onboarding import onboard_application
from core.questionnaire import ANNEX_III_AREAS, PROHIBITED_PRACTICES, Questionnaire
from core.store import Store

AUTONOMY = {
    "fully_automated": "Fully automated: outcomes take effect without a person reviewing them",
    "human_reviews": "A person reviews outcomes before they take effect",
    "advisory_only": "Advisory only: output is information, a person decides",
}


def render(store: Store) -> None:
    st.title("Onboard an application")
    st.caption("Tell us about the application. The answers drive the risk tier.")
    frameworks = st.session_state.get("frameworks", [])

    with st.form("onboard"):
        st.subheader("1. Application")
        name = st.text_input("Application name")
        st.caption("Give the code either as a public repository URL or as a folder on this machine.")
        url = st.text_input("Repository URL", placeholder="https://github.com/owner/repo",
                            help="Public repositories only. The code is fetched read-only and never run.")
        c1, c2 = st.columns(2)
        repo = c1.text_input("…or repository folder", help="Local path to the application's source code.")
        docs = c2.text_input("Documents folder (optional)",
                             help="Model cards, policies, data notes. Documents inside the repository are found automatically.")

        st.subheader("2. What it does")
        purpose = st.text_area("Intended purpose", placeholder="e.g. Ranks job applicants' CVs for recruiters.")
        role = st.radio("Your role", ["provider", "deployer"], horizontal=True,
                        format_func=str.capitalize,
                        help="Provider builds the system. Deployer uses a system built by someone else.")
        eu_market = st.checkbox("Placed on the market or used in the EU", value=True)
        area = st.selectbox("Does it operate in any of these areas?", list(ANNEX_III_AREAS),
                            format_func=ANNEX_III_AREAS.get)
        safety = st.checkbox("It is a safety component of a regulated product (machinery, medical device, vehicle, toys...)")
        affects = st.checkbox("Its output is used to make or support decisions about individual people")
        autonomy = st.radio("Level of human involvement", list(AUTONOMY), format_func=AUTONOMY.get)
        narrow = st.checkbox("It only performs a narrow procedural or preparatory task, with no real influence on outcomes")

        st.subheader("3. Transparency")
        interacts = st.checkbox("People interact with it directly (chat, voice, ...)")
        synthetic = st.checkbox("It generates synthetic text, image, audio or video")

        st.subheader("4. Prohibited practices screen")
        st.caption("Tick anything that applies. This should normally be empty.")
        prohibited = [k for k, label in PROHIBITED_PRACTICES.items() if st.checkbox(label, key=f"pp_{k}")]

        submitted = st.form_submit_button("Save application", type="primary")

    if submitted:
        q = Questionnaire(purpose=purpose, role=role, eu_market=eu_market, annex_iii_area=area,
                          safety_component_annex_i=safety, affects_individuals=affects,
                          autonomy=autonomy, narrow_procedural_task=narrow,
                          interacts_with_people=interacts, generates_synthetic_content=synthetic,
                          prohibited_practices=prohibited)
        try:
            with st.spinner("Fetching repository…" if url.strip() else "Saving…"):
                record = onboard_application(store, name=name, repo_path=repo, repo_url=url, docs_path=docs,
                                             questionnaire=q, frameworks=frameworks, user=st.session_state.user,
                                             samples_dir=ROOT / "samples")
        except ValueError as exc:  # includes FetchError
            for line in str(exc).splitlines():
                st.error(line)
            return
        st.session_state.flash = f"Saved '{record.name}'."
        st.session_state.page = "home"
        st.rerun()

    if st.button("Cancel"):
        st.session_state.page = "home"
        st.rerun()
