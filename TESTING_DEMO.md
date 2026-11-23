# Testing the onboarding demo

## 1. Automated checks (2 min)

```powershell
pip install -r requirements.txt
pytest                      # all tests, including tests/test_ui_flow.py (drives the real UI headlessly)
python scripts/check_demo.py   # must end with DEMO READY (needs demo/replay_cache.jsonl)
```

If `check_demo.py` reports missing recordings, record once: set the Azure keys and `PROVENIX_LLM_MODE=live`
in `.env`, run `python scripts/record_demo.py`, then switch back to `replay`.

## 2. Click-through without Azure (5 min, placeholder results)

1. In `.env` set `PROVENIX_LLM_MODE=fake`. Delete `data/`. Run `streamlit run main.py`.
2. Sign in, pick **EU AI Act**.
3. **Onboard an application** and fill in the Loan Pre-Approval Assistant values from `DEMO_SCRIPT.md`.
4. Check, as you answer, that the right-hand preview changes:
   - Area *Access to essential services* gives **High risk · Annex III 5(b)**.
   - Role *Both* adds Article 26. Ticking *creditworthiness* adds Article 27.
   - Expected: **16 of 21 rules** apply.
5. **Save**. You land on **Rule scope**. Remove Article 49 with a reason, add one custom rule, **Finalise**.
6. **Run** shows 16 rules (15 after the removal, plus any custom rule). Start the assessment.
7. **Review**: confirm one finding, override another (a note is required).
8. **Dashboard**: the headline, score and status bar update. **Report**: download and open the HTML.

## 3. Full demo (replay mode)

Set `PROVENIX_LLM_MODE=replay` and repeat step 2 using the exact values in `DEMO_SCRIPT.md`. Replay answers only
prompts it has seen, so paste the purpose text exactly. Expected: the Article 10 trap is detected on the loan app
(`data_sheet.md` says postcode is excluded, `features.py` uses `postcode_risk`).

## 4. What to look for in the new UI

- Sign-in page explains the product in three lines.
- Each application shows a title with chips (framework, tier, scope, assessed) and a 5-step tracker.
- Dashboard opens with a one-line verdict and a status bar before any detail.
- Review shows the status bar for the current decisions above the filters.

## Known gaps

- `tests/test_ui_flow.py` and the visual layout were not run in the build environment (Streamlit could not be
  installed there). Open the app once and check spacing in both light and dark themes.
