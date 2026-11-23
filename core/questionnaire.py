"""Questionnaire answers used by the rule-based risk-tier classifier."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Annex III areas (EU AI Act). The key is stored; the label is shown to users.
ANNEX_III_AREAS: dict[str, str] = {
    "none": "None of the areas below",
    "biometrics": "Biometrics (identification, categorisation, emotion recognition)",
    "critical_infrastructure": "Critical infrastructure (energy, traffic, water, digital)",
    "education": "Education and vocational training",
    "employment": "Employment, workers management, recruitment",
    "essential_services": "Access to essential services (credit, insurance, benefits, emergency)",
    "law_enforcement": "Law enforcement",
    "migration": "Migration, asylum and border control",
    "justice": "Administration of justice and democratic processes",
}

# Article 5 prohibited practices, as plain-language screening questions.
PROHIBITED_PRACTICES: dict[str, str] = {
    "manipulation": "Uses subliminal or deceptive techniques to distort people's behaviour in a harmful way",
    "exploit_vulnerabilities": "Exploits vulnerabilities of people due to age, disability or social/economic situation",
    "social_scoring": "Scores or classifies people by social behaviour or traits, leading to unfair treatment",
    "crime_prediction": "Predicts criminal offences of a person based only on profiling or personality traits",
    "face_scraping": "Builds facial recognition databases by untargeted scraping of images",
    "emotion_workplace_education": "Infers emotions of people in the workplace or in education (except medical or safety reasons)",
    "biometric_categorisation": "Categorises people by biometrics to infer sensitive traits (race, religion, orientation, etc.)",
    "realtime_remote_biometrics": "Real-time remote biometric identification in public spaces for law enforcement",
}

Role = Literal["provider", "deployer", "provider_and_deployer"]
ROLE_LABELS: dict[str, str] = {
    "provider": "Provider: we build it and put it on the market or into service",
    "deployer": "Deployer: we use a system someone else built",
    "provider_and_deployer": "Both: we build it and use it ourselves",
}
Autonomy = Literal["fully_automated", "human_reviews", "advisory_only"]


class Questionnaire(BaseModel):
    purpose: str = ""
    role: Role = "provider"
    eu_market: bool = True
    annex_iii_area: str = "none"
    safety_component_annex_i: bool = False
    affects_individuals: bool = False
    autonomy: Autonomy = "advisory_only"
    narrow_procedural_task: bool = False  # Art. 6(3) style exemption claim
    interacts_with_people: bool = False
    generates_synthetic_content: bool = False
    prohibited_practices: list[str] = Field(default_factory=list)
    # Added for rule scoping. Defaults keep older saved questionnaires valid.
    public_body_or_service: bool = False  # deployer is a public body or a private entity providing public services
    credit_or_insurance: bool = False  # creditworthiness / credit score, or life and health insurance pricing
    emotion_or_biometric_categorisation: bool = False
    deep_fake: bool = False  # generates or manipulates image, audio or video that could pass as real
    gpai_model: bool = False  # we provide a general-purpose AI model to others
    gpai_systemic_risk: bool = False

    @property
    def is_provider(self) -> bool:
        return self.role in ("provider", "provider_and_deployer")

    @property
    def is_deployer(self) -> bool:
        return self.role in ("deployer", "provider_and_deployer")

    @property
    def fria_trigger(self) -> bool:
        """Article 27 applies to public bodies / public-service providers and to credit or insurance uses."""
        return self.public_body_or_service or self.credit_or_insurance

    def problems(self) -> list[str]:
        out = []
        if len(self.purpose.strip()) < 10:
            out.append("Describe the system's intended purpose (at least a sentence).")
        if self.annex_iii_area not in ANNEX_III_AREAS:
            out.append("Unknown Annex III area.")
        unknown = set(self.prohibited_practices) - set(PROHIBITED_PRACTICES)
        if unknown:
            out.append(f"Unknown prohibited practices: {sorted(unknown)}")
        if self.gpai_systemic_risk and not self.gpai_model:
            out.append("A model with systemic risk must also be a general-purpose AI model.")
        return out
