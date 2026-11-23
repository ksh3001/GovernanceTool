# Risk register: Loan Pre-Approval Assistant

| ID | Risk | Mitigation | Owner |
|----|------|------------|-------|
| R1 | Unfair outcomes for protected groups | Quarterly fairness review (see model card) | Head of Credit Risk |
| R2 | Customer believes a pre-approval is a final offer | Wording reviewed by Legal; advisor confirms every offer | Product Owner |
| R3 | Model performance degrades | Weekly approval-rate monitoring (monitoring.py) | Model Owner |
| R4 | Chat collects data it does not need | Fixed question list in assistant.py | Data Protection Officer |
