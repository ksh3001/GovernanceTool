# Data notes: CV Screener

## Data processed
Applicant CVs submitted through the careers site. CVs contain names, contact
details, work history and education. The tool does not use special-category data
on purpose, but CV text can contain it.

## Source and collection
Candidates upload their own CV and agree to the privacy notice at submission.

## Handling
- CVs are stored in the applicant tracking system, not in the screening tool.
- Decision records are kept for 12 months and then deleted.
- No model training is done on candidate data.

## Quality
CV text is passed to the model unchanged. No other preparation is done.
