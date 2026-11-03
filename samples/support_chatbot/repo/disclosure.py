"""Messages that make clear to customers that they are talking to an AI."""

DISCLOSURE_MESSAGE = (
    "Hi! I'm an AI assistant, not a human. I can help with orders, delivery and "
    "returns. Type 'agent' at any time to talk to a person."
)


def handoff_message() -> str:
    return "No problem, I'm connecting you with a human colleague. Please wait a moment."
