# Model card: Support Chatbot

## Intended purpose
Answers customers' routine questions about orders, delivery and returns on the
shop's website. It does not make decisions about individual customers.

## Model
A commercial language model (gpt-4o-mini) with a fixed prompt, answering only from
the shop's FAQ. No fine-tuning.

## Limitations
- It can only answer questions covered by the FAQ.
- It may misread unusual phrasing and then offers a human agent.
