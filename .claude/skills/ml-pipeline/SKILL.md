---
name: ml-pipeline
description: Staged, leakage-safe workflow for tabular ML projects. The stages are EDA → grain definition → validated joins → feature engineering with a data dictionary → comparing candidate targets → baselines and a first model. Use this skill whenever the user wants to explore a dataset, join relational CSVs or tables, build features or a modeling table, decide "what can we predict", pick a target, check for data leakage, or train and evaluate a first model on tabular data, even if they don't say "pipeline" (e.g. "do some EDA on these CSVs", "what could we predict with this?", "build me a feature table", "train a delay model").
---

# ML pipeline

The work moves from raw tables to a modeling table that lets the user decide **what** to predict. Modeling comes after that decision. Do the stages in order, and produce one concrete deliverable per stage. Each stage depends on decisions made in the one before it: joins depend on the grain, features depend on the prediction time, and model results mean nothing if features leak.

If the project has a CLAUDE.md, its specifics override the generic defaults here (paths, environment, table names, prefixes).

## Stage 1: EDA
For each table, report:
- shape, dtypes, null %, duplicates (full rows and the candidate key), cardinality
- date ranges and value distributions

Check key relationships **before** joining:
- Is the key unique?
- Are there orphan keys (child rows whose key is missing from the parent)?
- What is the fan-out (how many child rows per parent row, i.e. 1:N)?

Keep an explicit **findings list** of anomalies. Common ones:
- nulls that are structural (e.g. no delivery date because the order was never delivered)
- timestamps out of order
- outliers
- codes that don't join (look for a pattern, e.g. a whole month using a different ID scheme)
- translation gaps

Record each anomaly with its count and the decision taken. Never silently drop rows.

When codes don't join, try to recover a mapping from the data itself before giving up. One way is votes from records that appear in both ID schemes. Validate the recovered mapping: does it cover every code, is it one-to-one, and do known pairs check out?

Plots: one message per plot, with a title that states that message. Label the axes. Check the numbers behind any claim in a title before writing it.

## Stage 2: Grain (decide BEFORE joining)
- State the grain of every table in one line, e.g. `orders: 1 row per order_id`, `items: 1 row per (order_id, item_id)`.
- Choose ONE target grain for the modeling table and write it at the top of the notebook or module.
- Different questions need different grains (order, customer, seller, product, line item…). Compare them; don't just assume one.
- Watch out for IDs that look like a person or entity but are really per-transaction (e.g. a per-order customer_id vs. the real customer's ID).

## Stage 3: Joins
- Build outward from the grain table with `how="left"`, unless there's a documented reason not to.
- **Aggregate child tables to the grain key before joining**, to avoid multiplying rows.
- Pass `validate="one_to_one"` / `"many_to_one"` to every `pd.merge`.
- Log row counts before and after each join, and assert `len(out) == len(left)` plus uniqueness of the grain key. See `references/snippets.md`.
- Tables with many rows per key (e.g. geolocation per zip prefix) get aggregated first, e.g. median lat/lng.

## Stage 4: Features
- Parse every timestamp to datetime. Express durations as float days or minutes.
- Group features by theme with a name prefix (e.g. `ord_`, `item_`, `pay_`, `cust_`, `sched_`, `hist_`, `ops_`). Candidate targets get the `tgt_` prefix and are kept separate from features.
- Every feature goes in a **data dictionary**: definition, source columns, null handling, and `available_at`. See `references/templates.md`.
- Handle nulls deliberately: either keep the NaN and add an indicator flag, or impute. Record which choice you made and why.
- Check timezones. If timestamps are local to different places, only compare times in the same zone, or convert explicitly. Otherwise "before the prediction time" is wrong, and the feature quietly leaks.

## Stage 5: Candidate targets ("what can we predict?")
Build several candidate targets and compare them in one table. For each, give:
- grain
- type (classification or regression)
- class balance or distribution
- missing rate and usable rows
- prediction time
- the main signal available at that time
- leakage risk

End with a recommendation for what to predict first, and why. Before calling a target predictable, check class imbalance and date coverage.

## Leakage rules (the part that most often goes wrong)
- **Every candidate target needs a prediction time.** Only information known at that moment is allowed as a feature. The same target at two different prediction times gives two different models with different feature sets; keep them separate.
- Tag every feature with `available_at` and assert that no post-prediction column appears in the feature matrix.
- **Historical aggregates:**
  - For val/test rows, use only data from before the prediction time or the training cutoff.
  - For training rows, compute target-based encodings out-of-fold (e.g. leave-one-month-out), so a row never sees its own label.
- **Split time-based problems by time, not randomly.** Calendar features the model never sees in training (e.g. month, when test months are unseen) are useless or misleading. Drop them, or replace them with something that generalizes (e.g. days to a holiday).
- **Verify with brute force:** recompute a random sample (~100–300 rows) of each complex feature with a plain loop, and assert it matches the vectorized version. This is what catches subtle off-by-one-window and timezone leaks.
- Full checklist: `references/leakage-checklist.md`.

## Stage 6: Baselines and first model (only after the target is chosen)
- Always fit at least two baselines before the real model:
  - a historical-rate lookup table, e.g. the target rate per category × hour
  - a linear or logistic model
- A boosted model that doesn't beat them isn't adding anything. Say so plainly.
- Pick the main metric to fit the problem: PR-AUC for imbalanced classes (report the base rate next to it), ROC-AUC, calibration, MAE for regression. Report validation and test separately.
- Watch for warning signs:
  - **Early stopping after a handful of trees:** the train/val distributions differ, or there's no signal. Try more regularization once; if it doesn't help, report it as a limit of the data.
  - **Suspiciously high scores:** look for leakage first.
  - **Mean prediction ≠ actual rate on test:** the base rate shifted, so recalibrate before the probabilities are used directly.
- Interpret results with feature importance (by gain), and connect it back to the EDA findings.

## Conventions
- Keep notebooks linear and rerunnable top to bottom. Once logic is stable, move it into `src/` modules (loading, mappings, feature builders) and import it from notebooks.
- Execute the notebook headlessly to verify, e.g. `jupyter nbconvert --to notebook --execute --inplace <nb>`, and scan the outputs for errors.
- Keep notebook outputs light: no large inline dumps, and a modest figure DPI.
- Set random seeds. Prefer vectorized pandas; loops over groups are fine, loops over rows are not (except in brute-force checks).
- Save artifacts to `outputs/`: feature tables, the data dictionary, metrics CSVs.
- Raw data is read-only. Don't add dependencies or restructure the repo without asking. Commit only when asked.

## Definition of done (exploration phase)
1. EDA findings list (issues + decisions).
2. Grain of each table documented; joins validated with assertions.
3. Feature table at the chosen grain, plus a data dictionary with `available_at`.
4. Candidate-target comparison table and a recommendation.
