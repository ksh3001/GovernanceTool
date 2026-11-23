# Provenix demo script: leadership walk-through (about 15 minutes)

This script is for the presenter. The demo runs from a saved recording, so it works without internet or Azure.

The story has three parts: answer a questionnaire, which decides the rules; agree the rules, then assess the
code against them; get a report a person has signed off.

## Before the demo

1. **Record once, live.** Fill in the Azure keys and set `PROVENIX_LLM_MODE=live` in `.env`, then run
   `python scripts/record_demo.py`. This assesses all three sample apps: HR CV Screener, Support Chatbot and
   Loan Pre-Approval Assistant. It prints the results and their agreement with the answer keys. Read them,
   then commit `demo/replay_cache.jsonl`.
2. **Check it offline.** Run `python scripts/check_demo.py`. It must end with **DEMO READY**.
3. In `.env`, set `PROVENIX_LLM_MODE=replay`.
4. Delete the `data/` folder for a clean start, then run `streamlit run main.py`.

Re-record (step 1) after any change to the questionnaire answers of a sample, the control pack, the prompts or
the sample files. Each of these changes the prompts, so the saved answers stop matching.

## Part 1: a new application, from questionnaire to rules (5 min)

| Step | Do | Say |
|---|---|---|
| 1. Sign in | Enter your name and pick **EU AI Act**. Point at the greyed-out ISO 42001 and NIST AI RMF. | "One framework is fully built. The pack structure takes more." |
| 2. Onboard | Click **＋ Onboard an application** and fill in the values in the table below. **Watch the live preview on the right as you answer.** | "The answers decide the risk tier and which of the 21 EU AI Act rules apply. Watch the count change." |
| 3. Show the logic | While filling in: choose the area *Access to essential services*, so the tier becomes **High risk · Annex III 5(b)**. Switch the role from *Provider* to *Both* and show Article 26 (deployer duties) appear. Tick *assesses creditworthiness* and show Article 27 (fundamental rights impact assessment) appear. | "Providers and deployers have different duties. A bank that builds and runs its own credit tool has both, plus a rights impact assessment." |
| 4. Save | Click **Save application**. You land on **step 1 · Rule scope**. | |
| 5. Agree the rules | Show **16 rules in scope** and the reason next to each one. Show the **Not applicable** list with the reason each rule was ruled out. | "Nothing is a black box. Every rule in or out has a reason." |
| 6. Remove a rule | On **Article 49 · Registration**, click **Remove**, give the reason *"Registration is handled centrally by the group regulatory team"*, and confirm. | "People stay in charge of the scope. Every change needs a reason and goes in the audit trail and the report." |
| 7. Custom rule (optional) | Open **Add a custom rule** and add, for example, *Bank policy CR-12 · Adverse action reasons: every declined applicant receives the main reasons for the decline in writing.* | "Internal policies can be checked the same way." In replay mode a custom rule has no recording, so it shows *insufficient evidence* with a note. Say so, or remove it before finalising. |
| 8. Finalise | Click **Finalise scope**. | "Only now can the assessment run." |

### Values for the Loan Pre-Approval Assistant

Use exactly these values. Replay only answers prompts it has seen, and the purpose text is part of the prompt,
so paste it rather than typing it.

| Field | Value |
|---|---|
| Application name | `Loan Pre-Approval Assistant` |
| Repository URL | leave empty |
| …or repository folder | `<path to GovernanceTool>\samples\loan_assistant\repo` |
| Documents folder | `<path to GovernanceTool>\samples\loan_assistant\docs` |
| Intended purpose | `Chat assistant that collects personal-loan applications from retail customers and gives an indicative pre-approval based on a credit score.` |
| Role | Both: we build it and use it ourselves |
| Placed on the market or used in the EU | ticked |
| Area | Access to essential services (credit, insurance, benefits, emergency) |
| Safety component | unticked |
| Output used for decisions about people | ticked |
| Human involvement | Fully automated |
| Narrow procedural task | unticked |
| Public body / public services | unticked |
| Creditworthiness or insurance pricing | **ticked** |
| People interact with it directly | **ticked** |
| Synthetic content, emotion recognition, deep fakes | unticked |
| General-purpose AI model | unticked |
| Prohibited practices | none |

The app is fictional (Meridian Bank). It is not added by **Load sample apps**, so the onboarding in front of
leadership is real. Because you point at the bundled folder, Provenix attaches its expert answer key, and the
agreement score appears in part 3.

## Part 2: run and review (6 min)

| Step | Do | Say |
|---|---|---|
| 9. Run | **Step 2 · Run**: show files found, the token estimate, and the 15 rules about to be assessed. Click **Start assessment**. | "Rules out of scope are recorded without a model call." |
| 10. Dashboard | Show the tier, the score, the status chart and the top gaps with their proposed solutions. | "The score is our internal metric, not an official rating." |
| 11. The trap | **Step 3 · Review**: open **Article 10 · Data governance**. It shows the data sheet saying *postcode is excluded to avoid proxy discrimination*, and `features.py` feeding a postcode default-rate feature to the model. | "The documents say one thing and the code does another. The model points at the lines, our code copies the text, and a second check confirms it. The quote cannot be invented." |
| 12. Human decision | Confirm Article 10. Override one finding (e.g. Article 27 to *Partial*) with a note, then show the score change on the Dashboard. | "The reviewer's decision is recorded, and the tool's own answer is kept." |
| 13. Organisational duties | Point at the *insufficient evidence* results (QMS, conformity assessment, incident reporting). | "These are organisational duties. They are proved by documents, not code. Supply the documents and they get assessed." |

## Part 3: the report and the evidence it is right (3 min)

| Step | Do | Say |
|---|---|---|
| 14. Agreement | Dashboard › **Agreement with the expert**. | "This compares the tool with our written answer key. It's a draft key until an expert confirms it." Rules you changed in the scope are left out of this number. |
| 15. Report | **Step 5 · Report**: show the **Assessment scope** section (rules in and out, your removal and its reason, who finalised it), then the findings with evidence and reviewer decisions. Download it. | "One self-contained file. Print it to PDF." |
| 16. Contrast (optional) | **Load sample apps** and open the Support Chatbot. Its scope is only 2 rules: AI literacy and the AI-disclosure duty. | "A different questionnaire gives a different set of rules. It doesn't over-flag." |

## What not to claim

- Don't quote an accuracy figure unless it comes from `record_demo.py` against a **confirmed** key. Say how
  many controls it covers.
- If asked, say the run is a **replay**. The dashboard says so on screen.
- The questionnaire simplifies the legal tests. A lawyer should confirm the scope for a real system, and the
  scope step exists for exactly that.
- Other apps behave worse than the samples. The rules and prompts were tuned on these three.
- The control pack is a draft until an expert signs it off.

## If something goes wrong

| Problem | Fix |
|---|---|
| "No recorded response" on Start assessment | The questionnaire answers, folders or scope differ from the recording. Check the values above, or run `python scripts/check_demo.py`. |
| Start assessment is missing | The scope isn't finalised yet. Go to step 1 and click **Finalise scope**. |
| A yellow banner says the scope changed | The scope was reopened after the run. Run the assessment again. |
| The page is stuck or looks odd | Refresh. State is saved in `data/`. |
| Wrong state after a rehearsal | Stop Streamlit, delete `data/`, and start again. |
| You need to show it with no recording at all | Set `PROVENIX_LLM_MODE=fake`. Results are placeholders and are labelled as such. Say so. |

## Rehearsal log

- [ ] Rehearsal 1: date ______ time taken ______ problems ______
- [ ] Rehearsal 2: date ______ time taken ______ problems ______
