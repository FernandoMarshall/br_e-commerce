"""Loading, cleaning and feature builders for the USDOT 2015 flight-delays dataset.

All raw times are LOCAL to the airport they refer to. Day-of features therefore only
compare times at the flight's own origin airport (same time zone); times from other
airports are shifted into origin-local time with each flight's own schedule-derived
time-zone difference (`tz_shift_min`).
"""
import os

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

ROUTE = ["ORIGIN_AIRPORT", "DESTINATION_AIRPORT"]

# Only known once the flight has departed (or later) -> never valid delay-prediction features
POST_DEPARTURE_COLS = [
    "DEPARTURE_TIME", "DEPARTURE_DELAY", "TAXI_OUT", "WHEELS_OFF", "ELAPSED_TIME", "AIR_TIME",
    "WHEELS_ON", "TAXI_IN", "ARRIVAL_TIME", "ARRIVAL_DELAY", "DIVERTED", "CANCELLED",
    "CANCELLATION_REASON", "AIR_SYSTEM_DELAY", "SECURITY_DELAY", "AIRLINE_DELAY",
    "LATE_AIRCRAFT_DELAY", "WEATHER_DELAY",
]


def load_flights(path):
    """Read flights/airlines/airports CSVs into a dict. Airport codes as str, DATE added."""
    dfs = {
        # Airport columns mix IATA codes and numeric BTS IDs (October) -> force str
        "flights": pd.read_csv(os.path.join(path, "flights.csv"),
                               dtype={"ORIGIN_AIRPORT": str, "DESTINATION_AIRPORT": str}),
        "airlines": pd.read_csv(os.path.join(path, "airlines.csv")),
        "airports": pd.read_csv(os.path.join(path, "airports.csv")),
    }
    flights = dfs["flights"]
    flights["DATE"] = pd.to_datetime(flights[["YEAR", "MONTH", "DAY"]])
    return dfs


def _vote(pairs):
    """pairs[num, iata] -> most-voted iata per num, with vote share."""
    vc = pairs.value_counts().rename("n").reset_index()
    vc["share"] = vc["n"] / vc.groupby("num")["n"].transform("sum")
    return vc.sort_values("n", ascending=False).drop_duplicates("num").set_index("num")


def _endpoint_pairs(merged, cols):
    return pd.concat([merged[[f"{c}_num", f"{c}_iata"]].set_axis(["num", "iata"], axis=1) for c in cols])


def map_october_airports(flights, airports):
    """Replace October's numeric BTS airport IDs with IATA codes, in place.

    Pass 1: the same (airline, flight no., sched. departure, distance) in Sep/Nov flies the
    same route -> each match votes numeric->IATA for origin and destination.
    Pass 2: codes left unmapped are matched on (airline, distance, mapped other endpoint)
    against all other months, excluding IATA codes already taken (mapping is 1:1).
    Adds AIRPORT_CODE_INFERRED and returns the mapping table.
    """
    is_oct = flights["MONTH"] == 10
    num_codes = set(pd.unique(flights.loc[is_oct, ROUTE].values.ravel()))

    key1 = ["AIRLINE", "FLIGHT_NUMBER", "SCHEDULED_DEPARTURE", "DISTANCE"]
    oct1 = flights.loc[is_oct, key1 + ROUTE].drop_duplicates()
    ref1 = flights.loc[flights["MONTH"].isin([9, 11]), key1 + ROUTE].drop_duplicates()
    map1 = _vote(_endpoint_pairs(oct1.merge(ref1, on=key1, suffixes=("_num", "_iata")), ROUTE))

    key2 = ["AIRLINE", "DISTANCE"]
    unmapped = num_codes - set(map1.index)
    oct2 = flights.loc[is_oct, key2 + ROUTE].drop_duplicates()
    ref2 = flights.loc[~is_oct, key2 + ROUTE].drop_duplicates()
    pairs2 = []
    for unk, other in [ROUTE, ROUTE[::-1]]:
        q = oct2[oct2[unk].isin(unmapped)].copy()
        q[other] = q[other].map(map1["iata"])
        pairs2.append(_endpoint_pairs(q.merge(ref2, on=key2 + [other], suffixes=("_num", "_iata")), [unk]))
    pairs2 = pd.concat(pairs2)
    map2 = _vote(pairs2[~pairs2["iata"].isin(map1["iata"])])

    code_map = pd.concat([map1.assign(pass_no=1), map2.assign(pass_no=2)])
    assert set(code_map.index) == num_codes, num_codes - set(code_map.index)
    assert code_map["iata"].is_unique
    assert code_map["iata"].isin(airports["IATA_CODE"]).all()
    known = {"10397": "ATL", "13930": "ORD", "12892": "LAX", "11298": "DFW", "14747": "SEA", "12478": "JFK"}
    assert all(code_map.loc[k, "iata"] == v for k, v in known.items())

    flights["AIRPORT_CODE_INFERRED"] = is_oct.astype(int)
    for c in ROUTE:
        flights.loc[is_oct, c] = flights.loc[is_oct, c].map(code_map["iata"])
    return code_map


def _hhmm_to_min(hhmm):
    return (hhmm // 100) * 60 + hhmm % 100


def add_times(flights, lead_hours=2):
    """Add local datetimes, the per-flight time-zone shift, and the prediction time, in place.

    sched_dep_dt / act_dep_dt are origin-local; sched_arr_dt / act_arr_dt are destination-local.
    tz_shift_min = destination UTC offset - origin UTC offset (minutes), from the schedule.
    pred_dt = sched_dep_dt - lead_hours (origin-local): the day-of prediction time.
    """
    dep_min = _hhmm_to_min(flights["SCHEDULED_DEPARTURE"])
    arr_min = _hhmm_to_min(flights["SCHEDULED_ARRIVAL"])
    # Arrival day offset: tz differences are < 12 h, so the nearest whole day is the right one
    day_off = np.round((dep_min + flights["SCHEDULED_TIME"] - arr_min) / 1440)
    flights["sched_dep_dt"] = flights["DATE"] + pd.to_timedelta(dep_min, unit="min")
    flights["sched_arr_dt"] = flights["DATE"] + pd.to_timedelta(arr_min + 1440 * day_off, unit="min")
    flights["tz_shift_min"] = ((flights["sched_arr_dt"] - flights["sched_dep_dt"]).dt.total_seconds() / 60
                               - flights["SCHEDULED_TIME"])
    flights["act_dep_dt"] = flights["sched_dep_dt"] + pd.to_timedelta(flights["DEPARTURE_DELAY"], unit="min")
    flights["act_arr_dt"] = flights["sched_arr_dt"] + pd.to_timedelta(flights["ARRIVAL_DELAY"], unit="min")
    flights["pred_dt"] = flights["sched_dep_dt"] - pd.Timedelta(hours=lead_hours)


def schedule_features(flights):
    """sched_*: known from the published schedule (days ahead). Adds columns in place."""
    flights["sched_airline"] = flights["AIRLINE"].astype("category")
    flights["sched_origin"] = flights["ORIGIN_AIRPORT"].astype("category")
    flights["sched_dest"] = flights["DESTINATION_AIRPORT"].astype("category")
    flights["sched_dep_hour"] = flights["SCHEDULED_DEPARTURE"] // 100
    flights["sched_arr_hour"] = flights["SCHEDULED_ARRIVAL"] // 100
    flights["sched_dow"] = flights["DAY_OF_WEEK"]
    flights["sched_block_min"] = flights["SCHEDULED_TIME"]
    flights["sched_distance"] = flights["DISTANCE"]

    dates = pd.DatetimeIndex(flights["DATE"].unique())
    hol = USFederalHolidayCalendar().holidays("2014-11-01", "2016-02-28")
    gap = np.abs((dates.values[:, None] - hol.values[None, :]) / np.timedelta64(1, "D")).min(axis=1)
    flights["sched_days_to_holiday"] = flights["DATE"].map(pd.Series(gap, index=dates))

    # Congestion from the schedule itself (cancelled flights were still scheduled)
    flights["sched_origin_hour_deps"] = flights.groupby(
        ["ORIGIN_AIRPORT", flights["sched_dep_dt"].dt.floor("h")])["MONTH"].transform("size")
    flights["sched_dest_hour_arrs"] = flights.groupby(
        ["DESTINATION_AIRPORT", flights["sched_arr_dt"].dt.floor("h")])["MONTH"].transform("size")


def history_features(flights, target, train_mask, groups, m=50):
    """hist_<name>_late_rate / hist_<name>_n: smoothed historical target rate per key group.

    Non-train rows use all training rows (strictly earlier months). Training rows use the
    other training months only (out-of-fold by month) so a row never sees its own label.
    Rates are shrunk towards the training mean with weight m.
    """
    prior = flights.loc[train_mask, target].mean()
    train = flights.loc[train_mask]
    is_train = train_mask.to_numpy()
    for name, keys in groups.items():
        tot = train.groupby(keys)[target].agg(s="sum", n="count").reset_index()
        by_month = train.groupby(keys + ["MONTH"])[target].agg(ms="sum", mn="count").reset_index()
        st = (flights[keys + ["MONTH"]]
              .merge(tot, on=keys, how="left", validate="many_to_one")
              .merge(by_month, on=keys + ["MONTH"], how="left", validate="many_to_one"))
        s = st["s"].fillna(0).to_numpy() - np.where(is_train, st["ms"].fillna(0), 0)
        n = st["n"].fillna(0).to_numpy() - np.where(is_train, st["mn"].fillna(0), 0)
        flights[f"hist_{name}_late_rate"] = (s + prior * m) / (n + m)
        flights[f"hist_{name}_n"] = n


def _window_stats(ev_key, ev_t, ev_v, q_key, q_t, window):
    """Per query (key, t): count and sum of ev_v over events with the same key and t - window < ev_t <= t."""
    ev = pd.DataFrame({"k": ev_key, "t": ev_t, "v": ev_v}).dropna().sort_values(["k", "t"])
    q = pd.DataFrame({"k": q_key, "t": q_t})
    q_t_ns = q["t"].to_numpy().astype("datetime64[ns]").astype(np.int64)
    w = np.int64(pd.Timedelta(window).value)
    n_out = np.zeros(len(q))
    s_out = np.zeros(len(q))
    q_idx = q.groupby("k").indices
    for k, e in ev.groupby("k"):
        if k not in q_idx:
            continue
        idx = q_idx[k]
        t = e["t"].to_numpy().astype("datetime64[ns]").astype(np.int64)
        cs = np.concatenate([[0.0], np.cumsum(e["v"].to_numpy(dtype=float))])
        hi = np.searchsorted(t, q_t_ns[idx], side="right")
        lo = np.searchsorted(t, q_t_ns[idx] - w, side="right")
        n_out[idx] = hi - lo
        s_out[idx] = cs[hi] - cs[lo]
    return n_out, s_out


def dayof_features(flights, window="3h"):
    """ops_*: known on the day of operation at pred_dt (origin-local). Adds columns in place.

    Inbound leg = latest leg of the same tail scheduled to arrive at this flight's origin
    within 12 h before its scheduled departure. Its actual times are only used if they
    happened by pred_dt.
    """
    t = flights["pred_dt"]
    has_tail = flights["TAIL_NUMBER"].notna()

    # Legs of the same aircraft earlier that day (schedule-based; tails are assigned on the day)
    flights["ops_tail_leg_num"] = (flights[has_tail].sort_values("sched_dep_dt")
                                   .groupby(["TAIL_NUMBER", "DATE"]).cumcount() + 1)

    left = (flights.loc[has_tail, ["TAIL_NUMBER", "ORIGIN_AIRPORT", "sched_dep_dt"]]
            .reset_index().sort_values("sched_dep_dt"))
    right = (flights.loc[has_tail & flights["sched_arr_dt"].notna(),
                         ["TAIL_NUMBER", "DESTINATION_AIRPORT", "sched_arr_dt", "sched_dep_dt",
                          "act_dep_dt", "act_arr_dt", "tz_shift_min", "DEPARTURE_DELAY", "ARRIVAL_DELAY"]]
             .rename(columns={"DESTINATION_AIRPORT": "ORIGIN_AIRPORT", "sched_dep_dt": "inb_sched_dep",
                              "act_dep_dt": "inb_act_dep", "act_arr_dt": "inb_act_arr",
                              "tz_shift_min": "inb_tz", "DEPARTURE_DELAY": "inb_dep_delay",
                              "ARRIVAL_DELAY": "inb_arr_delay"})
             .sort_values("sched_arr_dt"))
    inb = pd.merge_asof(left, right, left_on="sched_dep_dt", right_on="sched_arr_dt",
                        by=["TAIL_NUMBER", "ORIGIN_AIRPORT"], direction="backward",
                        tolerance=pd.Timedelta(hours=12)).set_index("index").reindex(flights.index)

    tz = pd.to_timedelta(inb["inb_tz"], unit="min")
    inb_sched_dep_local = inb["inb_sched_dep"] + tz     # inbound departure, in this origin's local time
    inb_act_dep_local = inb["inb_act_dep"] + tz
    found = inb["sched_arr_dt"].notna()
    departed = inb_act_dep_local <= t
    arrived = inb["inb_act_arr"] <= t

    flights["ops_inb_status"] = np.select([arrived, departed, found], [3, 2, 1], 0)  # 0 none, 1 not departed
    flights["ops_inb_sched_turn_min"] = (flights["sched_dep_dt"] - inb["sched_arr_dt"]).dt.total_seconds() / 60
    flights["ops_inb_arr_delay"] = inb["inb_arr_delay"].where(arrived)
    flights["ops_inb_dep_delay"] = inb["inb_dep_delay"].where(departed)
    # Not departed yet but scheduled before pred_dt -> already at least this late
    overdue = ((t - inb_sched_dep_local).dt.total_seconds() / 60).clip(lower=0)
    flights["ops_inb_known_delay"] = (flights["ops_inb_arr_delay"]
                                      .fillna(flights["ops_inb_dep_delay"])
                                      .fillna(overdue.where(found & ~departed)))
    flights["ops_inb_delay_minus_turn"] = flights["ops_inb_known_delay"] - flights["ops_inb_sched_turn_min"]

    # Airport state in the window before pred_dt (all times local to the origin airport)
    arr_late = (flights["ARRIVAL_DELAY"] > 15).astype(float).where(flights["ARRIVAL_DELAY"].notna())
    n, s = _window_stats(flights["DESTINATION_AIRPORT"], flights["act_arr_dt"], arr_late,
                         flights["ORIGIN_AIRPORT"], t, window)
    flights["ops_origin_arr_n"] = n
    flights["ops_origin_arr_late_rate"] = np.where(n > 0, s / np.maximum(n, 1), np.nan)
    n, s = _window_stats(flights["ORIGIN_AIRPORT"], flights["act_dep_dt"], flights["DEPARTURE_DELAY"],
                         flights["ORIGIN_AIRPORT"], t, window)
    flights["ops_origin_dep_n"] = n
    flights["ops_origin_dep_delay_mean"] = np.where(n > 0, s / np.maximum(n, 1), np.nan)
