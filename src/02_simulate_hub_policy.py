"""
Discrete-event simulation of outbound dispatch operations at Delhivery's Gurgaon
hub (Gurgaon_Bilaspur_HB, Haryana) - the highest-volume source hub in the real
dataset - for Medium-distance-tier shipments (77-299 km OSRM distance), the tier
where BOTH route types (Carting and FTL) are genuinely used in the real data,
making it the real decision point for a route-type policy question.

Real inputs (from 01_clean_data.py / clean_legs.csv):
  - Interarrival gaps between real historical dispatches at this hub/tier.
  - Paired (actual_time, osrm_time) bootstrapped jointly per route_type, so the
    real actual-vs-planned relationship for that mode is preserved (no fabricated
    independence between the two).

Model: a limited pool of outbound vehicles (SimPy Resource) at the hub. A dispatch
must acquire a vehicle for the duration of its real bootstrapped actual_time before
it can depart; when dispatches cluster (as they really do - interarrival gaps are
bootstrapped from the real, bursty historical pattern) a queue forms, adding real
queueing delay on top of transit time. This is exactly the value of a DES over a
plain Monte-Carlo draw: it captures hub congestion, not just transit-time variance.

Question: for a fixed SLA promise (deliver within 2x the OSRM-planned time - close
to the ~2.1-2.5x average delay ratio actually observed in this data), what is the
minimum outbound fleet size needed to hit a 90% on-time rate, under an All-Carting,
All-FTL, or Historical-mix (55% Carting / 45% FTL, the real observed split) policy?

Caveat stated up front: this dataset has no cost/fare field, so "cost" here is
proxied by vehicle-hours consumed (sum of actual_time), not currency - a fleet-size
recommendation is the honest deliverable, not a fabricated $ figure.
"""
import numpy as np
import pandas as pd
import simpy
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = Path(__file__).resolve().parent.parent / "output"
OUT.mkdir(exist_ok=True)

HUB = "Gurgaon_Bilaspur_HB (Haryana)"
SLA_BUFFER = 2.0          # promise: deliver within 2x the OSRM-planned time
TARGET_ON_TIME = 0.90
HORIZON_MIN = 60 * 24 * 30  # simulate 30 days
N_REPS = 80

legs = pd.read_csv(DATA / "clean_legs.csv")
hub_legs = legs[legs["source_name"] == HUB].copy()
q = hub_legs["osrm_distance"].quantile([0, 1 / 3, 2 / 3, 1]).values
hub_legs["tier"] = pd.cut(hub_legs["osrm_distance"], bins=q, labels=["Short", "Medium", "Long"], include_lowest=True)
med = hub_legs[hub_legs["tier"] == "Medium"].sort_values("od_start_time").reset_index(drop=True)

pools = {rt: med[med["route_type"] == rt][["actual_time", "osrm_time"]].values for rt in ["Carting", "FTL"]}
starts = pd.to_datetime(med["od_start_time"]).values.astype("datetime64[m]").astype(float)
gaps = np.diff(np.sort(starts))
gaps = gaps[gaps >= 0]
hist_carting_share = (med["route_type"] == "Carting").mean()

print(f"Hub: {HUB}")
print(f"Medium-tier legs: {len(med)}  (Carting={len(pools['Carting'])}, FTL={len(pools['FTL'])})")
print(f"Historical Carting share at Medium tier: {hist_carting_share:.2%}")
print(f"Median interarrival gap: {np.median(gaps):.1f} min | mean: {np.mean(gaps):.1f} min")


def draw_leg(rng, route_type):
    row = pools[route_type][rng.integers(0, len(pools[route_type]))]
    return float(row[0]), float(row[1])  # actual_time, osrm_time (minutes)


def run_sim(n_vehicles, policy, seed):
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    fleet = simpy.Resource(env, capacity=n_vehicles)
    log = []

    def dispatch_proc(dispatch_id):
        ready_time = env.now
        if policy == "Historical":
            rt = "Carting" if rng.random() < hist_carting_share else "FTL"
        else:
            rt = policy
        actual_time, osrm_time = draw_leg(rng, rt)
        with fleet.request() as req:
            yield req
            wait = env.now - ready_time
            yield env.timeout(actual_time)
            total_time = env.now - ready_time
            on_time = total_time <= SLA_BUFFER * osrm_time
            log.append((rt, wait, actual_time, osrm_time, total_time, on_time))

    def generator():
        i = 0
        while True:
            gap = rng.choice(gaps) if len(gaps) else 60.0
            yield env.timeout(max(gap, 1.0))
            i += 1
            env.process(dispatch_proc(i))

    env.process(generator())
    env.run(until=HORIZON_MIN)

    if not log:
        return np.nan, np.nan, 0
    log_df = pd.DataFrame(log, columns=["route_type", "wait", "actual_time", "osrm_time", "total_time", "on_time"])
    return log_df["on_time"].mean(), log_df["wait"].mean(), len(log_df)


results = []
VEHICLE_GRID = [2, 3, 4, 5, 6, 8, 10, 14, 18, 24]
for policy in ["Carting", "FTL", "Historical"]:
    for nv in VEHICLE_GRID:
        on_time_rates, waits = [], []
        for r in range(N_REPS):
            otr, w, n = run_sim(nv, policy, seed=10_000 * r + nv * 31 + hash(policy) % 977)
            on_time_rates.append(otr)
            waits.append(w)
        results.append({"policy": policy, "n_vehicles": nv,
                         "on_time_rate": float(np.nanmean(on_time_rates)),
                         "avg_wait_min": float(np.nanmean(waits))})
        print(f"{policy:12s} vehicles={nv:2d}  on_time={np.nanmean(on_time_rates):.3f}  avg_wait={np.nanmean(waits):6.1f} min")

res_df = pd.DataFrame(results)
res_df.to_csv(OUT / "hub_policy_results.csv", index=False)

print("\nMinimum fleet size to reach 90% on-time rate, by policy:")
for policy in ["Carting", "FTL", "Historical"]:
    sub = res_df[res_df["policy"] == policy].sort_values("n_vehicles")
    hit = sub[sub["on_time_rate"] >= TARGET_ON_TIME]
    if len(hit):
        print(f"  {policy:12s}: {int(hit.iloc[0]['n_vehicles'])} vehicles")
    else:
        print(f"  {policy:12s}: not reached within grid (max tested {sub['n_vehicles'].max()})")

print("\nSaved:", OUT / "hub_policy_results.csv")
