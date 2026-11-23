# Model card: Loan Pre-Approval Assistant

## Intended purpose
Gives retail customers of Meridian Bank an indicative pre-approval for unsecured personal
loans between £1,000 and £25,000. The final offer is always confirmed by a lending advisor.

## Model
- Credit model: gradient-boosted trees (credit-gbm v2.3), trained in-house.
- Conversation: a commercial language model that only asks the application questions.

## Performance
- AUC 0.81 on a 2025 hold-out set of 22,000 applications.
- Calibrated: predicted and observed repayment rates are within 2 points in every score band.

## Fairness
Approval rates are compared across age bands and gender every quarter. The largest gap
in the last review was 4 points (age 18-24 vs 35-44).

## Limitations
- Not validated for self-employed applicants with less than two years of accounts.
- Not intended for secured lending or business loans.
