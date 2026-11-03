# Model card: CV Screener

## Intended purpose
The CV Screener helps the recruitment team at a mid-sized employer handle large
volumes of applications. It scores each CV from 0 to 100 against a job
description and decides whether the candidate is shortlisted or rejected.

## Model
A general-purpose commercial language model (gpt-4o-2024-08-06), used as-is with a
fixed prompt and temperature 0. We do not fine-tune or train any model.

## Inputs and outputs
- Input: plain-text CV and a job description.
- Output: a score (0-100) and a one-sentence summary.

## Known limitations
- Scores can vary for CVs written in unusual formats.
- The tool only reads English-language CVs.

## Version history
- v1.0: first internal release.
