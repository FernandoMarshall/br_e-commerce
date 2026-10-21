# Templates

## Findings list (EDA)
```markdown
**Data quality**
1. <issue>: <count / %>, <where>. Decision: <keep + flag / map / exclude, and why>.

**Patterns**
- <one-line finding with the number behind it>

**Candidate target(s)**: <target>, <balance>. Allowed signals at <prediction time>: ... Forbidden: ...
```

## Grain table
```markdown
| Table | Grain | Key unique? | Joins to grain via | Pre-aggregation |
|---|---|---|---|---|
| orders | 1 row per order_id | yes | — (grain table) | — |
| order_items | 1 row per (order_id, order_item_id) | yes | order_id | count, sum(price), sum(freight) |
```

## Data dictionary
```markdown
| Feature | Definition | Source columns | available_at | Null handling |
|---|---|---|---|---|
| ord_purchase_dow | Day of week of purchase | order_purchase_timestamp | purchase | none |
| hist_seller_late_rate | Smoothed late rate of the seller's earlier orders | orders, tgt_late | purchase | prior when no history |
```
Put prediction-time definitions and helper (non-feature) columns at the top.

## Candidate-target comparison
```markdown
| Target | Type | Grain | Prediction time | Balance / distribution | Usable rows | Missing | Main signal available | Leakage risk | Verdict |
|---|---|---|---|---|---|---|---|---|---|
```

## Model results
```markdown
| Model | Features (prediction time) | PR-AUC val | PR-AUC test | ROC-AUC test | Brier test |
|---|---|---|---|---|---|
| Lookup baseline | ... | | | | |
| Logistic | ... | | | | |
| GBM | ... | | | | |
```
Always state the test base rate next to PR-AUC.
