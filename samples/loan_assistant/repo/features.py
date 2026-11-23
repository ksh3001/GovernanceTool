"""Turns the customer's answers into model features."""

# Default rate by postcode district, from the 2019-2024 loan book.
POSTCODE_RISK = {
    "E1": 0.081, "E2": 0.074, "N15": 0.069, "SE15": 0.066,
    "SW3": 0.012, "W8": 0.015, "NW3": 0.018,
}
DEFAULT_POSTCODE_RISK = 0.035


def _district(postcode: str) -> str:
    return postcode.strip().upper().split(" ")[0]


def build_features(answers: dict[str, str]) -> dict[str, float]:
    amount = float(answers["amount"])
    income = float(answers["annual_income"])
    monthly_debts = float(answers["monthly_debts"])
    term = int(answers["term_months"])
    return {
        "loan_to_income": amount / max(income, 1.0),
        "debt_to_income": (monthly_debts * 12) / max(income, 1.0),
        "monthly_payment_ratio": (amount / term) / max(income / 12, 1.0),
        "employment_years": float(answers["employment_years"]),
        "postcode_risk": POSTCODE_RISK.get(_district(answers["postcode"]), DEFAULT_POSTCODE_RISK),
    }
