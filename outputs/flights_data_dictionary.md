# Flight delay model: data dictionary

**Grain:** 1 row per scheduled flight (`flights.csv`, 2015). Model rows are flights that arrived. Cancelled and diverted flights have no target, but they still count as events in `ops_*` features.

**Prediction times** (`available_at`):
- `schedule`: known when the schedule is published, days ahead. Allowed in model A and model B.
- `day_of`: known at `pred_dt` = scheduled departure − 2 h (origin-local time). Allowed in model B only.
- `post_departure`: known only after the flight leaves. **Never a feature.** Covers `DEPARTURE_*`, `TAXI_*`, `WHEELS_*`, `ELAPSED_TIME`, `AIR_TIME`, `ARRIVAL_*`, `DIVERTED`, `CANCELLED*` and the five delay-cause columns (`src/flights.py: POST_DEPARTURE_COLS`).

**Time zones:** raw times are local to their airport.
- `tz_shift_min` = scheduled arrival − scheduled departure − `SCHEDULED_TIME`, which gives the destination's UTC offset minus the origin's.
- Day-of features only compare times that are local to this flight's origin airport.

Code: `src/flights.py`. Model: `flight_model.ipynb`.

## Target
| Column | Definition | Source | Nulls |
|---|---|---|---|
| `tgt_late` | 1 if arrival delay > 15 min, else 0 | `ARRIVAL_DELAY` | NaN for cancelled/diverted flights; those rows are excluded and the count is logged in the notebook |

## Helper columns (not features)
| Column | Definition |
|---|---|
| `sched_dep_dt` / `act_dep_dt` | Scheduled / actual departure datetime, origin-local (`DATE` + `SCHEDULED_DEPARTURE`, + `DEPARTURE_DELAY`) |
| `sched_arr_dt` / `act_arr_dt` | Scheduled / actual arrival datetime, destination-local. The day rolls over when the schedule crosses midnight. |
| `tz_shift_min` | Destination minus origin UTC offset (min), from the schedule |
| `pred_dt` | `sched_dep_dt` − 2 h: the day-of prediction time |
| `split` | train = Jan–Aug, val = Sep–Oct, test = Nov–Dec |
| `AIRPORT_CODE_INFERRED` | 1 for October rows whose airport codes were mapped from numeric BTS IDs |

## Schedule features (`available_at = schedule`)
| Feature | Definition | Source | Null handling |
|---|---|---|---|
| `sched_airline` | Airline code (categorical) | `AIRLINE` | none |
| `sched_origin` / `sched_dest` | Origin / destination IATA code (categorical) | `ORIGIN_AIRPORT`, `DESTINATION_AIRPORT` (October mapped) | none |
| `sched_dep_hour` / `sched_arr_hour` | Scheduled local departure / arrival hour | `SCHEDULED_DEPARTURE`, `SCHEDULED_ARRIVAL` | none |
| `sched_dow` | Day of week (1 = Mon) | `DAY_OF_WEEK` | none |
| `sched_block_min` | Scheduled gate-to-gate minutes | `SCHEDULED_TIME` | 6 NaN, kept (LightGBM handles them; the logistic baseline imputes the median) |
| `sched_distance` | Route distance, miles | `DISTANCE` | none |
| `sched_days_to_holiday` | Days to the nearest US federal holiday | `DATE`, pandas `USFederalHolidayCalendar` | none |
| `sched_origin_hour_deps` | Scheduled departures from the origin in the same local hour (includes later-cancelled flights) | schedule | none |
| `sched_dest_hour_arrs` | Scheduled arrivals at the destination in the same local hour | schedule | NaN if `sched_arr_dt` is NaN |

## Historical features (`available_at = schedule`)
Smoothed late rate: (late + 50 × prior) / (n + 50), where the prior is the training late rate.
- **Val/test rows** use Jan–Aug only, i.e. strictly earlier months.
- **Training rows** use the *other* training months (out-of-fold by month), so a row never sees its own label.

| Feature | Key | Notes |
|---|---|---|
| `hist_route_late_rate`, `hist_route_n` | origin, destination | `_n` = number of flights behind the rate |
| `hist_flight_late_rate`, `hist_flight_n` | airline, flight number, origin | the same scheduled flight in other months |
| `hist_airline_hour_late_rate`, `hist_airline_hour_n` | airline, scheduled departure hour | also used as baseline 1 |
| `hist_origin_hour_late_rate`, `hist_origin_hour_n` | origin, scheduled departure hour | |

## Day-of features (`available_at = day_of`, model B only)
**Inbound leg:** the latest leg of the same `TAIL_NUMBER` that is scheduled to arrive at this flight's origin within the 12 h before this flight's scheduled departure. Its actual times are only used if they happened by `pred_dt`.

| Feature | Definition | Null handling |
|---|---|---|
| `ops_tail_leg_num` | Order of this flight among the aircraft's legs that day, by schedule | NaN if `TAIL_NUMBER` is missing (0.25%) |
| `ops_inb_status` | 0 = no inbound found, 1 = inbound not departed by `pred_dt`, 2 = departed, 3 = arrived | none |
| `ops_inb_sched_turn_min` | Scheduled minutes between the inbound arrival and this departure | NaN if no inbound |
| `ops_inb_dep_delay` | Inbound departure delay, if it departed by `pred_dt` | NaN otherwise (status says why) |
| `ops_inb_arr_delay` | Inbound arrival delay, if it arrived by `pred_dt` | NaN otherwise |
| `ops_inb_known_delay` | Best delay estimate known at `pred_dt`: arrival delay, else departure delay, else how far past its scheduled departure the inbound already is | NaN if no inbound |
| `ops_inb_delay_minus_turn` | `ops_inb_known_delay` − `ops_inb_sched_turn_min`; > 0 means the delay exceeds the turnaround buffer | NaN if no inbound |
| `ops_origin_arr_n`, `ops_origin_arr_late_rate` | Arrivals into the origin airport in the 3 h before `pred_dt`, and the share > 15 min late | rate NaN if no arrivals |
| `ops_origin_dep_n`, `ops_origin_dep_delay_mean` | Departures from the origin airport in the 3 h before `pred_dt`, and their mean departure delay | mean NaN if no departures |
