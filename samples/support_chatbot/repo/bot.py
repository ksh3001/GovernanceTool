"""Customer-support chatbot for an online shop. Sample application B. Fictional."""
import logging
import pathlib

import yaml

from disclosure import DISCLOSURE_MESSAGE, handoff_message
from llm_client import chat

CONFIG = yaml.safe_load(pathlib.Path(__file__).with_name("config.yaml").read_text())
KNOWLEDGE_BASE = pathlib.Path(__file__).with_name("faq.txt")

log = logging.getLogger("support_bot")
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = (
    "You answer questions about orders, delivery and returns using only the FAQ below. "
    "If the answer is not in the FAQ, say you do not know and offer a human agent.\n\nFAQ:\n%s"
)


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: list[tuple[str, str]] = []
        self.started = False

    def start(self) -> str:
        """First message of every conversation tells the user they are talking to an AI."""
        self.started = True
        log.info("session %s started", self.session_id)
        return DISCLOSURE_MESSAGE

    def ask(self, question: str) -> str:
        if not self.started:
            raise RuntimeError("call start() first so the AI disclosure is shown")
        if question.strip().lower() in CONFIG["handoff_keywords"]:
            return handoff_message()
        faq = KNOWLEDGE_BASE.read_text()
        answer = chat(SYSTEM_PROMPT % faq, question)
        self.history.append((question, answer))
        log.info("session %s answered a question", self.session_id)
        return answer
