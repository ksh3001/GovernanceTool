# Provenix POC-Lite: demo script (about 10 minutes)

For the person presenting. The demo runs from a saved recording, so it works without internet or Azure.

## Before the demo

1. `python scripts/check_demo.py` must end with **DEMO READY**. If it says the saved run no longer matches, record again with `python scripts/record_demo.py` (needs the Azure keys), read the results it prints, and commit `demo/replay_cache.jsonl`.
2. In `.env`: `PROVENIX_LLM_MODE=replay`. Leave the Azure values empty if you like; replay never uses them.
3. Delete the `data/` folder for a clean start, then `streamlit run main.py`.
4. Use **Load sample apps** (local folders), not the repo URL. The recording was made from the local folders, so that is the path replay can answer. The URL path is shown separately in step 7.

## Walk-through

| Step | Do | Say |
|---|---|---|
| 1. Sign in | Enter your name, pick **EU AI Act**. Point at the greyed-out ISO 42001 and NIST AI RMF. | "One fully built framework. The others are placeholders until a compliance expert reviews their controls." |
| 2. Load | Click **Load sample apps**. Two apps appear: an HR CV screener and a customer-support chatbot. | "Two small apps we built, with a known correct answer written down by us." |
| 3. Risk tier | Open the CV screener. Show the tier and the rule behind it. | "The tier is decided by fixed rules from the questionnaire, with the legal basis. The model does not decide it. Recruitment screening is Annex III, so high risk." |
| 4. Run | Open **Run**. Show files found, estimated tokens, the per-control file list. Click **Start assessment**. | "Before any model call you see what will be read. Controls that do not apply are decided by code." |
| 5. Dashboard | Show score, status chart, top gaps. | "The score is our own internal metric, not an official rating." |
| 6. Review | Open the Article 14 gap. Show the two citations: the code and the policy document. Open the line-numbered view. | "The policy says a human reviews every rejection. The code rejects automatically. The model names the lines, our code copies the text, so the quote cannot be invented. A second check then re-reads each citation." |
| 7. Human decision | Override one finding with a note, then show the score change. | "People stay in charge. The decision is recorded and the tool's own answer is kept." |
| 8. Agreement | Show **Agreement with the expert**. | "Against our written answer key. Say it is a draft key until an expert confirms it." |
| 9. Report | Open **Report**, download it. | "One self-contained file. Print to PDF." |
| 10. Chatbot | Open the second app, a limited-risk case with only a disclosure duty. | "A different tier gives a different set of controls." |

Optional, if the network is up: **Onboard**, paste `https://github.com/ksh3001/provenix-sample-support-chatbot`, and show that it clones and classifies. Do not click Start assessment on it in replay mode: its files differ from the local folder, so it has no recording.

## What not to claim

- Do not quote an accuracy figure unless it comes from `record_demo.py` against a **confirmed** key, and say how many controls it covers (9 per app, 7 and 1 model-assessed).
- Say the run is a **replay** if asked. The dashboard says so on screen.
- Other apps behave worse than the samples. The rules and prompts were tuned on these two.
- Large repos (hundreds of files) get partial coverage on some controls, and those show "insufficient evidence" on purpose.
- The control pack is a draft until an expert signs it off.

## If something goes wrong

| Problem | Fix |
|---|---|
| "No recorded response" on Start assessment | You are not on the sample apps from **Load sample apps**, or prompts changed since recording. Run `python scripts/check_demo.py`. |
| Page is stuck or odd | Refresh. State is saved in `data/`, so you will not lose the run. |
| Wrong state after a rehearsal | Stop Streamlit, delete `data/`, start again. |
| Need to show it with no recording at all | Set `PROVENIX_LLM_MODE=fake`. Results are placeholders and are labelled as such. Say so. |

## Rehearsal log

Run the whole table twice, start to finish, on the machine you will present from.

- [ ] Rehearsal 1: date ______ time taken ______ problems ______
- [ ] Rehearsal 2: date ______ time taken ______ problems ______
