# CLAUDE.md

Project: ML pipeline on the Olist Brazilian e-commerce dataset (9 relational CSVs in `datasets/`).
Goal of this phase: **explore, define grain, join, engineer variables, and produce a modeling-ready table that lets us decide WHAT to predict.** Modeling comes after that decision, not before.

## Environment
- Windows, PowerShell/Git Bash. Python venv in `.venv/` (don't commit it).
- Stack: pandas, numpy, matplotlib, seaborn, Jupyter notebooks. Add scikit-learn only when modeling starts.
- Raw data: `datasets/*.csv` (read-only; never edit or overwrite raw files). Do not re-download via kagglehub if local copies exist.
- `flight_delays.ipynb` and `test.ipynb` are side experiments, not part of this pipeline unless told otherwise.

## Pipeline stages (do them in order, one deliverable per stage)

### 1. EDA
- Per table: shape, dtypes, null %, duplicates, cardinality, date ranges, value distributions.
- Check key relationships before joining: uniqueness of keys, orphan keys, fan-out (1:N) between tables.
- Note anomalies explicitly (e.g. null delivery dates on non-delivered orders, timestamp order violations, outliers in price/freight, category-name translation gaps). Record them in a findings list; don't silently drop rows.
- Plots: readable titles/axis labels, one message per plot.

### 2. Grain definition (decide BEFORE joining)
- State the grain of every table in one line, e.g. `orders: 1 row per order_id`, `order_items: 1 row per (order_id, order_item_id)`, `customers: 1 row per customer_id (customer_unique_id identifies the real person)`.
- Choose ONE target grain for the modeling table and write it at the top of the notebook/module (candidates: order, customer_unique_id, seller, product, order-item). Different prediction questions need different grains; compare them rather than assuming.
- Every table joined to that grain must be pre-aggregated to it first. Assert row counts after every join (`len(out) == len(left)`) and uniqueness of the grain key.

### 3. Table joins
- Join order: build from the grain table outward; use `how="left"` from the grain table unless there is a documented reason.
- Aggregate child tables (items, payments, reviews) to the grain key BEFORE joining to avoid row explosion.
- Use `validate="one_to_one"` / `"many_to_one"` in `pd.merge`. Log row counts before/after.
- Customers: `customer_id` is per-order; use `customer_unique_id` for repeat-customer logic.
- Geolocation has many rows per zip prefix: aggregate (median lat/lng) per prefix before joining.

### 4. Variable creation
- Group features by theme and prefix names accordingly: `ord_`, `item_`, `pay_`, `rev_`, `cust_`, `sel_`, `prod_`, `geo_`, `tgt_` (candidate targets).
- Typical candidates: delivery delay vs. estimate, approval/shipping/delivery durations, freight ratio, price, item count, payment installments/type, review score, distance customer↔seller, category (translated to English), customer order count / recency, seller volume.
- Parse all timestamp columns to datetime; derive durations in days (float).
- Document each variable: definition, source columns, null handling. Keep this in a data dictionary (markdown or CSV in the repo).

### 5. Candidate targets ("what can we predict?")
Build target columns separately from features and evaluate each one:
- Late delivery (delivered > estimated) — classification
- Review score / low review (<=2) — classification
- Delivery time in days — regression
- Repeat purchase (customer has >1 order) — classification
- Order value / freight value — regression
- Order cancellation — classification
For each candidate report: grain, class balance / distribution, missing rate, number of usable rows, and available leading signal.

## Leakage rules (critical)
- Define a **prediction time** for each candidate target. Only features known at that moment are allowed.
  - e.g. predicting late delivery at purchase time: NO delivered/carrier timestamps, NO review data.
  - e.g. predicting review score: delivery outcome is allowed only if the prediction time is after delivery.
- Tag every feature with `available_at` (purchase / approval / shipped / delivered / post-review) in the data dictionary.
- For time-based problems split train/test by time, not randomly.
- Aggregates over a customer/seller must only use data before the prediction timestamp.

## Data quality conventions
- Never drop rows without logging the count and reason.
- Filter to `order_status == "delivered"` only where the target requires it, and state that explicitly.
- Handle nulls deliberately (keep NaN + indicator flag vs. impute); record the choice.
- Check class imbalance and date coverage for each target before concluding it's predictable.

## Code & notebook conventions
- Keep notebooks linear and rerunnable top-to-bottom. Put reusable logic (loading, join helpers, feature builders) into `src/` modules once stable, and import them from notebooks.
- Small helper pattern used in `eda.ipynb`: `dfs` dict keyed by short table names (`orders`, `items`, `payments`, `reviews`, `customers`, `sellers`, `products`, `geolocation`, `category_translation`).
- Save outputs to `outputs/` (e.g. `features_<grain>.parquet`, data dictionary); keep notebook outputs light — large inline dumps bloat the `.ipynb` (eda.ipynb is already ~1 MB).
- Set random seeds. Prefer vectorized pandas over row loops.
- Don't add dependencies or restructure the repo without asking.

## Definition of done for this phase
1. Findings summary from EDA (data quality issues + decisions).
2. Grain table documented, joins validated with assertions.
3. Feature table at chosen grain + data dictionary (with `available_at`).
4. Comparison table of candidate targets (grain, balance, usable rows, leakage risk) and a recommendation for what to predict first.

## Git
- Branch: `feature/EDA`; main branch is `main`. Don't commit raw data, `.venv/`, or large outputs. Commit only when asked.
