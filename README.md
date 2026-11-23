# Provenix (GovernanceTool)

Assesses an AI application's code and documents against the EU AI Act. The answers to a questionnaire decide
the risk tier and which rules apply. A reviewer agrees the rule scope, Provenix finds cited evidence for each
rule, a person confirms or overrides each finding, and the result is a downloadable report.

```
streamlit run main.py
```

## Flow

1. **Onboard.** Point at a repo folder or a public repo URL, then answer the questionnaire. A live preview
   shows the tier and the rules that apply.
2. **Rule scope.** Each rule in or out has a reason (risk tier, provider or deployer role, or a specific
   answer). Remove or add back rules, or add custom rules. Every change needs a reason. Finalise the scope.
3. **Run.** Each in-scope rule is assessed. The citations are copied from the files by code and checked by a
   second model call.
4. **Review.** Confirm or override each finding, with a note.
5. **Dashboard and report.** You get a compliance score (an internal metric), gaps with proposed solutions,
   agreement with an expert key (sample apps only), and an HTML report that includes the scope and its audit
   trail.

## Rule pack

`control_packs/eu_ai_act/controls.yaml` has 21 rules:

- **High-risk provider duties:** Articles 9–15, 17, 43 (with 47 and 48), 49, 72 and 73.
- **Deployer duties:** Articles 26 and 27.
- **Transparency duties:** Articles 50(1)–(4).
- **AI literacy:** Article 4.
- **General-purpose AI model duties:** Articles 53 and 55.

Each rule declares `applies_to_tiers`, `applies_to_roles` and an optional `applies_if` questionnaire flag, so
applicability is decided in code and never by the model. The pack is a **draft** until a compliance expert
reviews it.

## Sample apps (`samples/`)

| App | Tier | Use |
|---|---|---|
| HR CV Screener | High (Annex III 4(a)) | Added by **Load sample apps**. Trap: the oversight policy claims a human review that the code does not do. |
| Support Chatbot | Limited (Art. 50) | Added by **Load sample apps**. Shows the tool does not over-flag. |
| Loan Pre-Approval Assistant | High (Annex III 5(b)) | Onboard it live in the demo by filling in the questionnaire. Trap: the data sheet says postcode is excluded, but the code uses it. |

See `DEMO_SCRIPT.md` for the leadership walk-through, and `scripts/record_demo.py` and `scripts/check_demo.py`
for the offline replay.

## Tests

```
pytest
```
