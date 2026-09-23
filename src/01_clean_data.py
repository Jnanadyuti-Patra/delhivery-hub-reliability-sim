"""
Clean the real Delhivery logistics dataset (India's largest integrated logistics
provider; public operational data, Sep 12 - Oct 3 2018, 144,867 GPS/scan records
across Indian cities/states, released for a public data-science case study).

Each trip is scanned at multiple checkpoints, producing several rows per
(trip_uuid, source_center, destination_center) leg with cumulative actual_time /
osrm_time. We collapse each leg to its final cumulative snapshot (max actual_time)
to get one real actual-vs-planned transit time observation per leg.
"""
import pandas as pd
import numpy as np
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "delhivery_india.csv"
OUT = Path(__file__).resolve().parent.parent / "data" / "clean_legs.csv"

usecols = [
    "trip_uuid", "route_type", "source_center", "source_name",
    "destination_center", "destination_name", "od_start_time", "od_end_time",
    "start_scan_to_end_scan", "is_cutoff", "cutoff_factor",
    "actual_distance_to_destination", "actual_time", "osrm_time", "osrm_distance",
]
df = pd.read_csv(RAW, usecols=usecols)

# Collapse repeated checkpoint scans per (trip, source, destination) leg to the
# final cumulative snapshot -> one real actual-vs-planned time observation per leg.
grp = df.groupby(["trip_uuid", "source_center", "destination_center"], as_index=False).agg(
    route_type=("route_type", "first"),
    source_name=("source_name", "first"),
    destination_name=("destination_name", "first"),
    od_start_time=("od_start_time", "first"),
    od_end_time=("od_end_time", "first"),
    start_scan_to_end_scan=("start_scan_to_end_scan", "first"),
    actual_time=("actual_time", "max"),
    osrm_time=("osrm_time", "max"),
    osrm_distance=("osrm_distance", "max"),
    actual_distance_to_destination=("actual_distance_to_destination", "max"),
    is_cutoff_any=("is_cutoff", "max"),
    cutoff_factor_max=("cutoff_factor", "max"),
)

grp = grp[(grp["actual_time"] > 0) & (grp["osrm_time"] > 0) & (grp["osrm_distance"] > 0)]
grp["delay_ratio"] = grp["actual_time"] / grp["osrm_time"]          # >1 = slower than routing-engine plan
grp["delay_minutes"] = grp["actual_time"] - grp["osrm_time"]
# strip state name in parens for a cleaner city label, e.g. "Anand_VUNagar_DC (Gujarat)"
grp["source_city"] = grp["source_name"].str.extract(r"^([^_]+)")
grp["destination_city"] = grp["destination_name"].str.extract(r"^([^_]+)")

grp = grp[(grp["delay_ratio"] > 0) & (grp["delay_ratio"] < 10)]  # drop extreme data-entry outliers
grp.to_csv(OUT, index=False)

print(f"Raw scan rows: {len(df):,}")
print(f"Unique trip legs after collapsing checkpoints: {len(grp):,}")
print()
print("Route type share:")
print(grp["route_type"].value_counts())
print()
print("Actual transit time (minutes) by route type:")
print(grp.groupby("route_type")["actual_time"].agg(["count", "mean", "median", "std"]).round(1))
print()
print("Delay ratio (actual/osrm-expected) by route type:")
print(grp.groupby("route_type")["delay_ratio"].agg(["mean", "median", "std"]).round(3))
print()
top_hubs = grp["source_name"].value_counts().head(10)
print("Top 10 source hubs by leg volume:")
print(top_hubs)
