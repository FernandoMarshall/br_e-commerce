# Snippets

## Validated left join
```python
def checked_merge(left, right, on, validate="many_to_one", name=""):
    """Left-join that asserts no row explosion and logs counts."""
    out = left.merge(right, on=on, how="left", validate=validate, indicator=True)
    unmatched = (out.pop("_merge") == "left_only").sum()
    print(f"{name}: {len(left):,} -> {len(out):,} rows | unmatched: {unmatched:,}")
    assert len(out) == len(left)
    return out
```

## Aggregate a child table to the grain first
```python
items_agg = (items.groupby("order_id")
             .agg(item_n=("order_item_id", "size"), item_price_sum=("price", "sum"),
                  item_freight_sum=("freight_value", "sum")))
assert items_agg.index.is_unique
```

## Out-of-fold (by time period) smoothed target rate
```python
def oof_rate(df, keys, target, train_mask, period="MONTH", m=50):
    """Eval rows: all training data. Training rows: other training periods only."""
    prior = df.loc[train_mask, target].mean()
    tr = df[train_mask]
    tot = tr.groupby(keys)[target].agg(s="sum", n="count").reset_index()
    per = tr.groupby(keys + [period])[target].agg(ps="sum", pn="count").reset_index()
    st = (df[keys + [period]].merge(tot, on=keys, how="left", validate="many_to_one")
          .merge(per, on=keys + [period], how="left", validate="many_to_one"))
    is_tr = train_mask.to_numpy()
    s = st["s"].fillna(0).to_numpy() - np.where(is_tr, st["ps"].fillna(0), 0)
    n = st["n"].fillna(0).to_numpy() - np.where(is_tr, st["pn"].fillna(0), 0)
    return (s + prior * m) / (n + m)
```

## As-of join ("latest event before t", per key)
```python
# Both sides sorted by their time keys; no NaT allowed in either key.
pd.merge_asof(left.sort_values("t"), right.sort_values("event_t"),
              left_on="t", right_on="event_t", by="entity_id",
              direction="backward", tolerance=pd.Timedelta("12h"))
```

## Brute-force check of a vectorized feature
```python
rng = np.random.default_rng(42)
for i in rng.choice(df.index, 200, replace=False):
    r = df.loc[i]
    ev = events[(events["key"] == r["key"]) & (events["t"] > r["pred_t"] - window) & (events["t"] <= r["pred_t"])]
    assert len(ev) == r["feat_count"]
```
