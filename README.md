# churn-insights

Read the notes your CRM never made you read.

Customer Success teams write thousands of account notes a year. Almost nobody reads them in aggregate, because until recently nobody could. This tool does: it ingests a CRM export, analyzes churn against the structured fields, then uses an LLM to read the free-text CSM notes and surface the risk patterns that preceded churn.

Then it scores your live accounts against those same patterns.

> Your CRM said these accounts were healthy. Here is what the notes said in the 90 days before they left.

## Status

In development. Built in public, phase by phase.

- [x] Phase 0: Project skeleton
- [ ] Phase 1: Load and display a CRM export
- [ ] Phase 2: Structured churn analysis by segment, tenure, and ARR
- [ ] Phase 3: LLM extraction of risk themes from CSM notes
- [ ] Phase 4: Correlate themes to churn outcomes, score live accounts
- [ ] Phase 5: Deploy

## Data

All data in this repository is synthetic. It was generated to resemble a real B2B SaaS CRM export in structure, distribution, and note style. No real customer data is used anywhere in this project.

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
