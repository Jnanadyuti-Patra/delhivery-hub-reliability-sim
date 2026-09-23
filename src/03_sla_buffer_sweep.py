"""
Follow-up to 02_simulate_hub_policy.py: that experiment showed on-time rate
plateaus (~42-50%) well before fleet size stops mattering (queueing wait -> 0
by ~8-10 vehicles) - i.e. the bottleneck at a 2x-of-plan SLA is real transit-time
VARIANCE, not congestion. So instead of sweeping fleet size, fix fleet size at a
congestion-free level (12 vehicles) and sweep the SLA buffer itself to find the
promise window each route-type policy can actually deliver on 90% of the time.
"""
import numpy as np
import pandas as pd
import simpy
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = Path(__file__).resolve().parent.parent / "output"

HUB = "Gurgaon_Bilaspur_HB (Haryana)"
N_VEHICLES = 12   # congestion-free per the 02_ result (wait ~= 0 here for all policies)
TARGET_ON_TIME = 0.90
HORIZON_MIN = 60 * 24 * 30
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


def draw_leg(rng, route_type):
    row = pools[route_type][rng.integers(0, len(pools[route_type]))]
    return float(row[0]), float(row[1])


def run_sim(policy, sla_buffer, seed):
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    fleet = simpy.Resource(env, capacity=N_VEHICLES)
    log = []

    def dispatch_proc(dispatch_id):
        ready_time = env.now
        rt = ("Carting" if rng.random() < hist_carting_share else "FTL") if policy == "Historical" else policy
        actual_time, osrm_time = draw_leg(rng, rt)
        with fleet.request() as req:
            yield req
            yield env.timeout(actual_time)
            total_time = env.now - ready_time
            log.append(total_time <= sla_buffer * osrm_time)

    def generator():
        i = 0
        while True:
            gap = rng.choice(gaps) if len(gaps) else 60.0
            yield env.timeout(max(gap, 1.0))
            i += 1
            env.process(dispatch_proc(i))

    env.process(generator())
    env.run(until=HORIZON_MIN)
    return float(np.mean(log)) if log else np.nan


BUFFER_GRID = [1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 4.5, 5.0]
results = []
for policy in ["Carting", "FTL", "Historical"]:
    for buf in BUFFER_GRID:
        rates = [run_sim(policy, buf, seed=10_000 * r + int(buf * 100) + hash(policy) % 977) for r in range(N_REPS)]
        rate = float(np.nanmean(rates))
        results.append({"policy": policy, "sla_buffer": buf, "on_time_rate": rate})
        print(f"{policy:12s} buffer={buf:.2f}x  on_time={rate:.3f}")

res_df = pd.DataFrame(results)
res_df.to_csv(OUT / "sla_buffer_results.csv", index=False)

print(f"\nMinimum SLA buffer (x plan time) to reach {TARGET_ON_TIME:.0%} on-time, by policy:")
for policy in ["Carting", "FTL", "Historical"]:
    sub = res_df[res_df["policy"] == policy].sort_values("sla_buffer")
    hit = sub[sub["on_time_rate"] >= TARGET_ON_TIME]
    if len(hit):
        print(f"  {policy:12s}: {hit.iloc[0]['sla_buffer']:.2f}x plan time")
    else:
        print(f"  {policy:12s}: not reached within grid (max tested {sub['sla_buffer'].max()}x)")

print("\nSaved:", OUT / "sla_buffer_results.csv")
