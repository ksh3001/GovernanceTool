# Data sheet: credit-gbm v2.3

## Source
180,000 personal-loan applications made to Meridian Bank between 2019 and 2024, with
12-month repayment outcomes.

## Preparation
- Duplicates and withdrawn applications removed.
- Income and debt values above the 99.5th percentile capped.

## Features
Loan-to-income, debt-to-income, monthly payment ratio and years with current employer.

Postcode and nationality are deliberately excluded to avoid proxy discrimination.

## Bias testing
Approval rates by age band and gender are tested before each release and every quarter.
