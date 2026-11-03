"""EU AI Act risk-tier rules (Regulation (EU) 2024/1689). DRAFT: pending expert review.

Rules run in order and the first one that matches decides the tier.
The questionnaire is a simplification of the legal tests; the expert reviews
the mapping, including the Annex III sub-point keywords below.
"""
from core.questionnaire import ANNEX_III_AREAS, PROHIBITED_PRACTICES, Questionnaire
from core.tiers import RuleStep, TierResult

URL = "https://eur-lex.europa.eu/eli/reg/2024/1689/oj"

# Annex III area -> point number in Annex III.
ANNEX_POINT = {
    "biometrics": "1", "critical_infrastructure": "2", "education": "3", "employment": "4",
    "essential_services": "5", "law_enforcement": "6", "migration": "7", "justice": "8",
}

# Employment sub-point 4(a) is recruitment or selection; 4(b) covers decisions during employment.
RECRUITMENT_WORDS = ("recruit", "applicant", "candidate", "cv", "resume", "hiring", "shortlist", "job advert")


def _annex_basis(q: Questionnaire) -> str:
    point = ANNEX_POINT[q.annex_iii_area]
    if q.annex_iii_area == "employment":
        text = q.purpose.lower()
        point += "(a)" if any(w in text for w in RECRUITMENT_WORDS) else "(b)"
    return f"Annex III point {point}"


def classify(q: Questionnaire) -> TierResult:
    steps: list[RuleStep] = []

    def check(rule_id: str, question: str, matched: bool, detail: str = "") -> bool:
        steps.append(RuleStep(rule_id=rule_id, question=question, matched=matched, detail=detail))
        return matched

    def result(tier: str, rule_id: str, basis: str, reason: str) -> TierResult:
        return TierResult(tier=tier, rule_id=rule_id, legal_basis=basis, reason=reason,
                          source_url=URL, steps=steps)

    # 0. Scope (Art. 2)
    if check("scope", "Is the system placed on the EU market or its output used in the EU?", q.eu_market) is False:
        return result("out_of_scope", "scope", "Article 2",
                      "The system is not placed on the EU market or used in the EU, so the Act does not apply.")

    # 1. Prohibited practices (Art. 5)
    hits = [k for k in q.prohibited_practices if k in PROHIBITED_PRACTICES]
    if check("art5", "Does it use a practice prohibited by Article 5?", bool(hits),
             "; ".join(PROHIBITED_PRACTICES[k] for k in hits)):
        return result("prohibited", "art5", "Article 5",
                      f"Prohibited practice declared: {PROHIBITED_PRACTICES[hits[0]]}. "
                      "The system must not be placed on the market (a narrow set of exceptions exists for some law-enforcement uses).")

    # 2. High risk through product safety law (Art. 6(1))
    if check("art6_1", "Is it a safety component of a product covered by Annex I legislation?",
             q.safety_component_annex_i):
        return result("high", "art6_1", "Article 6(1) and Annex I",
                      "It is a safety component of a regulated product, which makes it high risk "
                      "(when that product needs third-party conformity assessment).")

    # 3. High risk through Annex III use cases (Art. 6(2)), with the Art. 6(3) exemption
    in_annex_iii = q.annex_iii_area != "none"
    if check("art6_2", "Does it operate in an Annex III area?", in_annex_iii, ANNEX_III_AREAS[q.annex_iii_area]):
        basis = _annex_basis(q)
        exempt = q.narrow_procedural_task and not q.affects_individuals
        check("art6_3", "Does the Article 6(3) exemption apply (narrow task, no profiling of people)?", exempt,
              "Claimed a narrow procedural task" + ("" if not q.affects_individuals
                                                    else ", but it affects individuals, so profiling cannot be ruled out"))
        if not exempt:
            return result("high", "art6_2", basis,
                          f"It operates in an Annex III area ({ANNEX_III_AREAS[q.annex_iii_area]}), "
                          f"covered by {basis}, so it is high risk.")
        steps_note = "The provider must document this assessment under Article 6(4)."
        return result(_limited_or_minimal(q), "art6_3", "Article 6(3)",
                      f"Annex III area, but the Article 6(3) exemption applies. {steps_note}")

    # 4. Transparency duties (Art. 50)
    duties = []
    if q.interacts_with_people:
        duties.append("interacts directly with people")
    if q.generates_synthetic_content:
        duties.append("generates synthetic content")
    if check("art50", "Does it have Article 50 transparency duties?", bool(duties), " and ".join(duties)):
        return result("limited", "art50", "Article 50",
                      f"It {' and '.join(duties)}, which carries transparency duties but no high-risk requirements.")

    # 5. Everything else
    check("minimal", "Anything else", True)
    return result("minimal", "minimal", "Article 95 (voluntary codes)",
                  "No prohibited practice, high-risk use or transparency duty applies.")


def _limited_or_minimal(q: Questionnaire) -> str:
    return "limited" if (q.interacts_with_people or q.generates_synthetic_content) else "minimal"
