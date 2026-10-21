# Leakage checklist

Run through this list before reporting any model result.

## Prediction time
- [ ] Each model has a stated prediction time (e.g. "at purchase", "2 h before scheduled departure").
- [ ] Each feature's `available_at` is at or before that time.
- [ ] Columns that are only filled *after* the outcome (delivered dates, review data, actual times, delay causes, cancellation reasons) are listed as forbidden. A test asserts that none of them are in the feature list.
- [ ] Status fields that encode the outcome (e.g. `order_status == delivered` when predicting delivery) are not used as features or as unexplained filters.

## Aggregates and encodings
- [ ] Customer/seller/route/entity aggregates for evaluation rows use only rows from before the prediction time or the training cutoff.
- [ ] Target encodings for training rows are out-of-fold (by time period or K-fold), so a row's own label never feeds its feature.
- [ ] A test recomputes one aggregate for val/test rows from training data only and asserts it matches.

## Time
- [ ] Train/val/test split by time when the problem is about the future.
- [ ] No feature uses values the model can't have seen in training (e.g. month, when test months are unseen).
- [ ] Timezones: compare timestamps in one zone. Local times from different places are converted or never compared.
- [ ] Rolling windows are half-open and end at the prediction time: `(t − w, t]`. Events exactly at or after t are excluded.
- [ ] Brute-force recomputation of windowed/as-of features on a random sample matches the vectorized version.

## Rows
- [ ] Dropped rows are logged with a count and a reason. Filters that depend on the outcome (e.g. "only delivered orders") are stated explicitly, and their effect on the target population is understood.
- [ ] Rows with no target are excluded from the model, but still used as events where they carry real information (e.g. a cancelled inbound flight).

## Sanity on results
- [ ] Results compared against a lookup baseline and a linear baseline.
- [ ] PR-AUC is reported next to the base rate.
- [ ] Unexpectedly strong features were checked for leakage before being reported as findings.
