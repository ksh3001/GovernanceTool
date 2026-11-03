# Provenix POC-Lite: plan for a leadership demo

Goal: in about 2 weeks, show leadership one AI app being assessed against the EU AI Act, with cited findings that a human confirms or overrides. It should look real and be easy to explain.

This is a simplified alternative to `IMPLEMENTATION_PLAN.md` (32 tasks, 6 weeks). `SPEC.md` is untouched. Anything cut here can come back in the full build.

## What leadership needs to see

1. **Framework choice:** after sign-in, the user picks the framework(s) to assess against.
2. **Input:** a short questionnaire plus an AI app (a local repo folder and a few documents). The two sample apps are the guaranteed demo path. Other small-to-medium apps can be onboarded through the same screen (see "Onboarding an app").
3. **Risk tier:** a clear, rule-based answer (e.g. "High risk, Annex III 4(a) employment") with the reason.
4. **Findings per control:** met / partial / not met / insufficient evidence, each with a **citation** (file, lines, exact excerpt).
5. **Human review:** the reviewer confirms or overrides each finding and adds a note.
6. **Dashboard:** per application, the risk tier, a compliance score and counts of controls by status.
7. **Report:** a downloadable summary (HTML/PDF).
8. **One agreement number:** "Provenix agreed with the expert on X of Y controls."

Everything else is plumbing, and leadership won't see it.

## Simplified stack

| Full plan | POC-Lite |
|---|---|
| Postgres + pgvector, Alembic | **No database.** Local files only: one folder per application under `data/apps/<app_id>/` holding `questionnaire.json`, `findings.json`, `review.json` and the run log. Pydantic models load and save them. Control pack stays in YAML |
| Redis + arq worker | Run synchronously with a progress bar |
| LangGraph + checkpointing | **A plain Python loop**: for each control, gather evidence, call LLM, verify |
| FastAPI + React + Vite + shadcn + openapi client | **Streamlit**, one Python app, no API/frontend split |
| Docker compose, WeasyPrint | Run locally with `streamlit run`. Report as HTML, with PDF via browser print |
| Embeddings and vector search | **File-relevance filter** (`relevance.py`): keyword scoring per control plus a token budget. No embeddings. See "Onboarding an app" |
| tree-sitter, PyMuPDF, python-docx | Read text and code files directly. PDF and docx text extraction is optional and degrades gracefully if the library is missing |
| Hexagonal ports/adapters, `llm_call` table | One `llm.py` wrapper that logs each call to a file |

Language: Python only. Core dependencies: `streamlit`, `openai` (Azure), `pydantic`, `pyyaml`, `jinja2`. Optional: `pymupdf` and `python-docx` for PDF/docx documents. Nothing else.

Configuration comes from environment variables (or a git-ignored `.env`): `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `PROVENIX_DEMO_PASSWORD`, and `PROVENIX_LLM_MODE` (`live`, `fake` or `replay`). Keys are never written to `data/` or the run log.

## What stays, because it makes the demo credible

- **Rule-based risk tier.** Plain Python rules. The LLM only explains the result.
- **Code-made citations.** The model picks a file and line range, and the code copies the excerpt and hashes it. The model never writes evidence text.
- **Untrusted content.** Repo and document text is wrapped in `<untrusted_content>` tags. Nothing from the analysed repo is executed.
- **Human override.** Every finding has a confirm/override control and a note.
- **Verifier step.** A second check confirms that each citation actually supports the finding. Findings that fail are downgraded to "insufficient evidence".

## Onboarding an app

The onboarding screen takes an application name, **either a public repository URL or a path to a local repo folder**, an optional path to a documents folder, and the questionnaire. Nothing from the app is executed.

**Repository URL (`fetch.py`).** Public repos only, on an allowed host (`github.com`, `gitlab.com`, `bitbucket.org`, configurable with `PROVENIX_GIT_HOSTS`). The URL must be plain `https://host/owner/repo` with no credentials, query or port. The tool runs a shallow clone (`--depth 1`, no tags, no submodules, no LFS content, HTTPS only, git prompts disabled) into `data/checkouts/<app_id>/` with a 120-second timeout and a 100 MB limit, and records the commit SHA so findings tie to an exact version. A failed fetch creates no application. Private repositories are out of scope for the POC. The clone happens once at onboarding and the local copy is reused, so a demo does not need the network afterwards.

**Sample apps as public repos.** The two sample apps are also published as public repos (`provenix-sample-hr-cv-screener`, `provenix-sample-support-chatbot`) so the URL path can be demonstrated. They hold the code and a `docs/` folder only. The answer keys stay in this tool repo under `samples/`, each with a `repo_url`, which is how a URL-onboarded sample is matched to its key. Apps from any other URL show "no expert key".

### Ingestion (`ingest.py`)

- **Walk the folder** and keep text and code files only. Skip `.git`, `node_modules`, `venv`, `dist`, `build`, `__pycache__`, lock files, binaries, images and any file over 200 KB.
- **Document types:** `.md`, `.txt`, `.rst` read directly. `.pdf` and `.docx` are extracted if the optional library is installed. If not, the file is listed as "not readable" in the run summary and is never silently dropped.
- **Record per file:** relative path, kind (`code`, `doc`, `config`), size, line count, and SHA-256. Line numbers are 1-based and are the basis of every citation.
- **Safety:** reject paths outside the chosen folder, do not follow symlinks, and cap total files at 500.

### File-relevance filter (`relevance.py`)

The filter decides which files go to the model for each control. It replaces vector search with plain, explainable keyword scoring.

1. **Keywords per control.** Each control in `controls.yaml` gets a `search_terms` list, for example logging: `log`, `audit`, `trace`, `retention`, `timestamp`. The expert reviewing the pack also reviews these.
2. **Score every file per control.** Score = weighted hits of the control's terms in the path (heavier) and in the content, plus a bonus for file kind that matches the control's `expected_evidence` (code, document, or both). Always keep `README*`, `config*` and any model card or policy file as low-priority candidates.
3. **Pick files under a budget.** Take the top-scoring files until the control's token budget is reached (default about 12,000 tokens, estimated as characters ÷ 4). A file that does not fit is trimmed to the best-matching line windows (matching lines plus about 20 lines of context each, merged), with the original line numbers kept.
4. **Small-app shortcut.** If the whole app fits in the budget, send everything. This keeps the two sample apps simple and deterministic.
5. **Always include a code and a document view.** At least one code file and one document are included when any exist, so the model can compare what a document claims with what the code does (the trap case in App A).
6. **Record the selection.** For each control the run log stores the files chosen, their scores, which were trimmed, and which were left out. The review screen shows "files considered" beside each finding.

### Honest limits

- If the best evidence is likely outside the budget (the top files were trimmed, or relevant files were left out), the finding carries a **coverage flag**. The model may not return "not met" on trimmed or partial evidence. It must return "insufficient evidence" and say that coverage was limited. Absence of evidence is only "not met" when the filter saw the whole app or no file scored above zero.
- Citations are still made by the code from the original file, so trimming never changes line numbers or excerpts.
- Keyword scoring misses evidence that uses unusual naming. This is a known limit and is stated in the dashboard footer and the report.
- Tested to roughly 5,000 lines and 100 files. Larger repos run but show a "partial coverage" banner.
- The agreement score exists only for apps that have an `answer_key.yaml` (A and B). For any other app the dashboard shows "no expert key available" instead of a number.

### Run summary

Before the assessment starts, the screen shows: files found, files used, files skipped (with reasons), unreadable documents, estimated token cost, and the coverage banner if any. The user confirms, then the run starts.

## What is cut

Any database, multi-tenancy, queues, graph checkpointing, vector search, prompt versioning infrastructure, tracing, `org_id` on every table, generated API clients, Docker. See the out-of-scope list in `CLAUDE.md`. Add the new cuts to it if you adopt this plan.

## Scope

- **Controls:** 8–10 EU AI Act controls in a YAML file (e.g. risk management Art. 9, data governance Art. 10, technical documentation Art. 11, logging Art. 12, transparency Art. 13, human oversight Art. 14, accuracy/robustness Art. 15, plus transparency duties Art. 50).
- **Sample apps:** 2, written by us, so the expected answers are known (details below).
- **Documents:** 2–3 short markdown/text files per app (e.g. a model card or an oversight policy).
- **Other apps:** any local repo folder can be onboarded through the same flow, within the limits above. One extra real or open-source app is run before the demo as a smoke test, not as part of the scripted demo.
- **Control schema:** each control in `controls.yaml` also carries `search_terms`, `expected_evidence`, `applies_to_tiers` (so "not applicable" is decided by code, not the model), and `source_url`.

## Choosing a framework

After a simple sign-in, the user picks which framework to assess the app against.

- **Sign-in:** a plain name and a shared demo password, or just a "who are you" box. It exists to put a reviewer name on overrides. There is no SSO and there are no roles.
- **Picker:** the onboarding screen lists the available frameworks from the `control_packs/` folder, so a new framework is a new folder and not a code change. The user can pick one or several.
- **Each framework is a pack** with its own `pack.yaml` (name, version, source, reviewer), `controls.yaml`, and `tier_rules.py` if the framework has risk tiers.
- **Per framework, the assessment runs separately.** Findings, dashboard, compliance score and report are kept per application and per framework.
- **Planned packs:**

| Pack | Status in this plan | Notes |
|---|---|---|
| EU AI Act | **Built**, 8–10 controls | Has risk tiers (prohibited, high, limited, minimal), so it uses the rule-based classifier |
| ISO/IEC 42001 | **Optional second pack, needs your decision** | A management-system standard, so it has no risk tier. Controls are clauses and Annex A controls. The standard text is paid, so we write short paraphrases and cite clause numbers only, and never copy the text |
| Others (NIST AI RMF, etc.) | **Shown as "coming soon" in the picker** | Greyed out, to show the design supports them |

The assessment loop, citations, verifier, review screen, dashboard and report all read from the pack, so they do not change per framework. Only the tier step is skipped for frameworks without tiers.

**Scope conflict:** `CLAUDE.md` lists ISO 42001 as an assessed framework under "Out of scope for the POC". The picker and the pack structure are cheap and are included. The ISO 42001 pack itself is shown as a stretch item (days 11–12) until you approve it, and `CLAUDE.md` needs updating if you do.

## Where the rules come from

The rules are not fetched live from any portal. The demo must not depend on the network, and the text must not change between runs.

- The source is the official text of **Regulation (EU) 2024/1689** on EUR-Lex.
- Each control in the YAML records: control id, article number, a short paraphrase of the obligation, a short quote, the EUR-Lex link, and the evidence we expect to find (code, document, or both).
- Risk-tier rules cite Article 5 (prohibited), Annex III (high risk) and Article 50 (transparency).
- A compliance expert reviews the YAML before the demo, and the file records who reviewed it and when. Until then, the demo labels the control pack "draft, pending expert review".

## Sample apps

Each app is small (under about 500 lines in total) so the whole app can be sent to the model. Each has an `answer_key.yaml` with the expected status for every control, and where the evidence is.

**App A: HR CV-screening tool (expected tier: high risk, Annex III 4(a) employment)**

| Part | Content |
|---|---|
| Code | `screen.py` (ranks CVs with an LLM call), `audit.py` (logging), `config.yaml` |
| Documents | `model_card.md`, `oversight_policy.md`, `data_notes.md` |
| Expected results | Logging (Art. 12): **met**. Technical documentation (Art. 11): **partial** (model card has no accuracy figures). Human oversight (Art. 14): **not met** (code auto-rejects candidates, no review step). Risk management (Art. 9): **insufficient evidence** (no document). Data governance (Art. 10): **partial** |
| Trap case | `oversight_policy.md` says "a human reviews every rejection", but `screen.py` rejects automatically. The tool should flag the document claim as not backed by the code |

**App B: customer-support chatbot (expected tier: limited risk, Art. 50)**

| Part | Content |
|---|---|
| Code | `bot.py` (answers questions), `disclosure.py` (tells users they are talking to AI), `config.yaml` |
| Documents | `model_card.md`, `transparency_note.md` |
| Expected results | Transparency (Art. 50(1)): **met**. Art. 50(2) marking: **not applicable** if the bot generates no synthetic media, otherwise assessed. High-risk controls (Arts. 9–15, including logging): **not applicable** at this tier, because the Act does not require them for limited-risk systems. (An earlier draft said "Logging: partial". That contradicted the N/A rule, so it was removed.) |
| Purpose | Shows that the tool does not over-flag a low-risk app |

The answer keys are written first (Day 3) and drafted by us. A compliance expert must confirm them before the agreement score is quoted to anyone.

## Compliance score and dashboard

Each application gets a dashboard page in the Streamlit app, built on Day 9.

- **Risk tier:** a badge, with the rule that set it.
- **Compliance score:** (met + 0.5 × partial) ÷ applicable controls, shown as a percentage. "Insufficient evidence" and "not met" count as 0. "Not applicable" controls are left out.
- **Status counts:** met / partial / not met / insufficient evidence, shown as a bar chart.
- **Top gaps:** the not-met and insufficient-evidence controls, each linking to its finding.
- **Reviewer view:** the score is calculated from the reviewer's final status where they have overridden a finding, and from the tool's status otherwise. The dashboard shows how many findings were overridden.
- **Labels:** the compliance score is our own metric, not an official EU measure, and the dashboard says so. It is separate from the **agreement score**, which measures how often Provenix matched the expert answer key.

The dashboard footer states the coverage level of the run (full, or partial with the number of files left out) and the keyword-search limit.

Single application only. A portfolio view across many applications stays out of scope.

## Plan (about 10 working days, 13 with the ISO 42001 stretch)

| Days | Deliverable | Done when |
|---|---|---|
| 1 | Skeleton: Streamlit app, `config` (env vars), `llm.py` wrapper with fake, live and replay modes, local JSON file store (`data/`), **sign-in and framework picker shell** (EU AI Act only, others greyed out) | `streamlit run` shows sign-in, then the picker, and a fake-LLM test passes |
| 2 | Control pack YAML (sourced from Regulation 2024/1689 on EUR-Lex, with `search_terms`, `applies_to_tiers`) and onboarding form with questionnaire | Every control has an article, quote, link and search terms. Questionnaire answers are saved per application |
| 3 | Sample apps A and B, their documents and `answer_key.yaml` files | Each app has a written answer key (control by control), including the trap case in A |
| 4 | Rule-based classifier | A and B get the expected tiers, with unit tests |
| 5 | **Ingestion and file-relevance filter**: folder walk, skip rules, optional PDF/docx, per-control scoring, token budget, line-window trimming, coverage flag, run summary screen | Unit tests: skip rules work, relevant files rank first, trimmed files keep original line numbers, the coverage flag is set when files are cut |
| 6–7 | Assessment loop: filtered files per control, call LLM, make citations in code | Findings with real excerpts appear for app A |
| 8 | Verifier step and guardrails (untrusted tags, downgrade on bad citation, no "not met" on partial coverage) | A fabricated-citation test and a truncated-evidence test both end in "insufficient evidence" |
| 9 | Review screen (findings list, citation viewer, files considered, confirm/override, notes) and dashboard (tier, compliance score, status counts, top gaps) | A reviewer can complete a full review, and the dashboard updates from overrides |
| 10 | Report page and download, agreement score against the answer keys, **smoke test on one extra real app** | Report downloads for A and B. Agreement score is shown for A and B. The extra app runs end to end and shows "no expert key" |
| 11–12 (stretch, if approved) | ISO 42001 pack: 8–10 controls, a third sample app or answer key for App B | The same app can be assessed against EU and ISO, and shows two dashboards |
| 13 | Demo hardening: cache a good run so the demo works without live LLM calls, write the script, rehearse | Two clean rehearsals |

The core plan is now 10 days with the filter included. Sign-in and the picker moved to Day 1 because every later screen needs a reviewer name and a chosen pack.

## Demo script (15 minutes)

1. Problem (2 min): EU AI Act obligations are slow and manual to check.
2. Sign in and pick a framework, then onboard app A (2 min): fill the questionnaire and point at the repo.
3. Tier (1 min): show the rule that fired.
4. Run the assessment (3 min): progress per control, then the findings table.
5. Open one finding (3 min): the exact excerpt, the file and lines, and the reasoning.
6. Override one finding (1 min): as the human reviewer.
7. Show the dashboard (tier, compliance score, top gaps), then the report and the agreement score (2 min).
8. Show a failure honestly (1 min): an "insufficient evidence" result, and why that is the safe default.

## Risks

- **Live LLM flakiness during the demo.** Mitigate with the cached run and a "replay" toggle.
- **Wrong or hallucinated findings.** The code-made citations and the verifier limit this. Keep the answer-key scoring so we can say how often it is right.
- **Framework creep.** Each extra framework needs its own expert-reviewed controls. Keep to one fully built pack plus, at most, one stretch pack.
- **Scope creep back to the full plan.** Anything not in the table above waits.
- **Legal credibility.** Have a compliance expert review the control pack and the answer keys, or the agreement number means little.
- **Keyword filter misses evidence.** Unusual naming can hide the right file. The coverage flag and "insufficient evidence" default keep this safe, and the files-considered list lets a reviewer see what the model saw.
- **Arbitrary apps behave worse than the samples.** The rules, prompts and search terms are tuned on A and B. Treat other apps as a smoke test, say so in the demo, and never quote an agreement score for them.
- **Cost and time per run.** About 10 controls × up to 12,000 tokens each. The run summary shows the estimate first, and the replay mode avoids live calls in the demo.
- **Misread score.** Leadership may take the compliance score as an official rating. Label it as an internal metric.

## Open decision

Streamlit is fastest. If leadership expects a polished product UI, add 3–4 days for a small React front end, but keep the Python side unchanged.
