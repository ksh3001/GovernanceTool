"""Customer chat for Meridian Bank's personal-loan pre-approval. Sample application C. Fictional.

Collects the application in a short conversation, then asks decision.py for a pre-approval.
"""
from decision import decide
from llm_client import chat  # thin wrapper around the bank's LLM endpoint

GREETING = (
    "Hello, I'm Meridian's virtual assistant. I'm an AI system, not a person. "
    "I can check whether you're likely to be pre-approved for a personal loan. "
    "Type 'advisor' at any time to speak to a member of our lending team."
)

QUESTIONS = [
    ("amount", "How much would you like to borrow?"),
    ("term_months", "Over how many months would you like to repay?"),
    ("annual_income", "What is your annual income before tax?"),
    ("monthly_debts", "How much do you pay each month towards other loans or cards?"),
    ("employment_years", "How many years have you been with your current employer?"),
    ("postcode", "What is your postcode?"),
]

SYSTEM_PROMPT = (
    "You help customers apply for a personal loan. Ask the next question politely. "
    "Never promise approval. Never give financial advice."
)


class Conversation:
    def __init__(self, applicant_id: str):
        self.applicant_id = applicant_id
        self.answers: dict[str, str] = {}
        self.step = 0

    def start(self) -> str:
        return GREETING

    def reply(self, message: str) -> str:
        if message.strip().lower() in {"advisor", "adviser", "human", "person"}:
            return "Of course. I'm passing you to a lending advisor now."
        if self.step > 0:
            key, _ = QUESTIONS[self.step - 1]
            self.answers[key] = message.strip()
        if self.step < len(QUESTIONS):
            _, question = QUESTIONS[self.step]
            self.step += 1
            return chat(SYSTEM_PROMPT, question)
        outcome = decide(self.applicant_id, self.answers)
        return outcome.customer_message
