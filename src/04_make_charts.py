import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = Path(__file__).resolve().parent.parent / "output"
plt.rcParams["figure.dpi"] = 200
plt.rcParams["savefig.dpi"] = 200
plt.rcParams["font.size"] = 10

legs = pd.read_csv(DATA / "clean_legs.csv")
fleet_res = pd.read_csv(OUT / "hub_policy_results.csv")
buf_res = pd.read_csv(OUT / "sla_buffer_results.csv")

# 1. delay ratio distribution by route type (national, all hubs)
fig, ax = plt.subplots(figsize=(6, 4))
for rt, color in [("Carting", "#4C72B0"), ("FTL", "#DD8452")]:
    d = legs[legs["route_type"] == rt]["delay_ratio"]
    d = d[d < d.quantile(0.98)]
    ax.hist(d, bins=40, alpha=0.55, label=f"{rt} (n={len(d):,})", color=color, density=True)
ax.axvline(1.0, color="gray", linestyle="--", linewidth=1, label="On-plan (ratio=1)")
ax.set_xlabel("Actual time / OSRM-planned time")
ax.set_ylabel("Density")
ax.set_title("Delhivery India: actual vs. planned transit time by route type\n(all hubs, Sep-Oct 2018, n=26,003 legs)")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "01_delay_ratio_distribution.png")
plt.close(fig)

# 2. fleet size vs on-time rate, per policy (Gurgaon hub, Medium tier)
fig, ax = plt.subplots(figsize=(6, 4))
for policy, color in [("Carting", "#4C72B0"), ("FTL", "#DD8452"), ("Historical", "#55A868")]:
    sub = fleet_res[fleet_res["policy"] == policy].sort_values("n_vehicles")
    ax.plot(sub["n_vehicles"], sub["on_time_rate"], marker="o", label=policy, color=color)
ax.axhline(0.90, color="gray", linestyle="--", linewidth=1, label="90% target")
ax.set_xlabel("Outbound vehicles at hub")
ax.set_ylabel("On-time rate (SLA = 2x plan time)")
ax.set_title("Gurgaon hub, Medium-distance tier:\non-time rate plateaus - fleet size is NOT the bottleneck")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "02_fleet_size_vs_ontime.png")
plt.close(fig)

# 3. SLA buffer vs on-time rate, per policy - the actionable recommendation chart
fig, ax = plt.subplots(figsize=(6, 4))
for policy, color in [("Carting", "#4C72B0"), ("FTL", "#DD8452"), ("Historical", "#55A868")]:
    sub = buf_res[buf_res["policy"] == policy].sort_values("sla_buffer")
    ax.plot(sub["sla_buffer"], sub["on_time_rate"], marker="o", label=policy, color=color)
ax.axhline(0.90, color="gray", linestyle="--", linewidth=1)
ax.set_xlabel("SLA promise (x OSRM-planned time)")
ax.set_ylabel("On-time rate")
ax.set_title("Gurgaon hub, Medium tier: SLA buffer needed to hit 90% on-time\nFTL reaches target at a tighter buffer than Carting")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "03_sla_buffer_vs_ontime.png")
plt.close(fig)

# 4. top hubs by leg volume
fig, ax = plt.subplots(figsize=(6.5, 4))
top = legs["source_name"].value_counts().head(10).sort_values()
ax.barh([s.split(" (")[0] for s in top.index], top.values, color="#4C72B0")
ax.set_xlabel("Outbound legs (Sep-Oct 2018)")
ax.set_title("Top 10 Delhivery source hubs by outbound leg volume")
fig.tight_layout()
fig.savefig(OUT / "00_top_hubs.png")
plt.close(fig)

print("Charts saved to", OUT)
for f in sorted(OUT.glob("*.png")):
    print(" -", f.name)
