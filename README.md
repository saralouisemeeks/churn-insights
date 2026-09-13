# churn-insights

Read the notes your CRM never made you read.

Customer Success teams write thousands of account notes a year. Almost nobody reads them in aggregate, because until recently nobody could. This tool does: it ingests a CRM export, analyzes churn against the structured fields, then uses an LLM to read the free-text CSM notes and surface the risk patterns that preceded churn.

Then it scores your live accounts against those same patterns.

> Your CRM said these accounts were healthy. Here is what the notes said in the 90 days before they left.

## Status

In development. Built in public, phase by phase.

- [x] Phase 0: Project skeleton
- [x] Phase 1: Load and display a CRM export
- [ ] Phase 2: Structured churn analysis by segment, tenure, and ARR
- [ ] Phase 3: LLM extraction of risk themes from CSM notes
- [ ] Phase 4: Correlate themes to churn outcomes, score live accounts
- [ ] Phase 5: Deploy

## Data

All data in this repository is synthetic. No real customer data is used anywhere in this project.

`scripts/generate_data.py` produces it and is committed so the generation method is auditable. It writes three files:

| File | Contents |
|---|---|
| `data/accounts.csv` | 220 accounts with the fields a CRM actually carries |
| `data/notes.csv` | 8,452 free-text CSM notes |
| `data/ground_truth.csv` | the risk themes actually injected per account |

`ground_truth.csv` is never read by the app. It exists so Phase 4 can measure how well the LLM recovers themes it was never shown, instead of grading its own homework.

The generator builds in three properties on purpose:

1. Risk signal lives in the notes, not the structured fields. If a column predicted churn, no LLM would be needed.
2. The CRM health score is poorly calibrated. 27% of churned accounts carry a healthy score, which is typical of real CRM hygiene.
3. Retained accounts show risk themes too, so churn is not linearly separable. The signal is in which themes co-occur and how recent they are.

## Stack

Python, Streamlit, Anthropic API.

## Running locally

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Author

Sara Meeks. Customer Success and CX leader.
