# Delhivery Hub Reliability & SLA Study

A discrete-event simulation study of real Indian logistics operations data, built to answer one question a network-design consultant would actually be asked: **when a hub misses its delivery promise, is it because there aren't enough vehicles, or because the promise itself is unrealistic?**

**[Live dashboard](https://jnanadyuti-patra.github.io/delhivery-hub-reliability-sim/)** · Data: [Delhivery](https://www.delhivery.com/) operational GPS/scan records (public case-study release, Sep–Oct 2018)

## Data

144,867 real scan-level records covering 26,003 trip legs across 1,487 source hubs in India, released by Delhivery (India's largest integrated logistics provider) for a public data-science case study. Each leg has a real actual transit time and an OSRM (routing-engine) planned time, plus a route type: **Carting** (smaller local pickup/delivery runs) or **FTL** (full truck load, long-haul).

Row count and field structure verified directly against the public dataset before use — no synthetic or fabricated records.

## Method

1. **`src/01_clean_data.py`** — collapses repeated checkpoint scans per trip leg to one real actual-vs-planned transit-time observation, and reports delay-ratio and transit-time stats by route type.
2. **`src/02_simulate_hub_policy.py`** — a SimPy discrete-event model of outbound dispatch at Gurgaon_Bilaspur_HB (the busiest hub in the data), with a limited vehicle pool (`simpy.Resource`) so dispatches genuinely queue when they cluster, exactly as real historical dispatches do (interarrival gaps are bootstrapped from the real data, not assumed). Sweeps fleet size from 2 to 24 vehicles under three route-type policies.
3. **`src/03_sla_buffer_sweep.py`** — the finding from step 2 (on-time rate plateaus long before queueing wait hits zero — fleet size is *not* the bottleneck) motivates the follow-up: fix fleet size at a congestion-free level and sweep the SLA promise itself to find what buffer each route-type policy can actually deliver on.
4. **`src/04_make_charts.py`** — report figures.
5. **`dashboard.html`** — interactive results dashboard (GitHub Pages).

All transit times and interarrival gaps used by the simulation are **bootstrapped from the real dataset** (paired actual/planned draws, preserving the real relationship between them) — not fitted theoretical distributions. The one caveat stated honestly: this dataset has no cost/fare field, so vehicle-hours (not currency) is used as the operational-efficiency proxy.

## Findings

- Real deliveries run **2.1–2.5x** the routing engine's naive planned time on average.
- Adding outbound vehicles does **not** fix on-time performance at a 2x-of-plan SLA — on-time rate plateaus (~42–50%) well before queueing wait reaches zero. The bottleneck is transit-time variance, not fleet capacity.
- At a fixed, congestion-free fleet size, **FTL reaches a 90% on-time rate at a 3.0x-of-plan SLA buffer**, versus **3.5x for Carting** or the historical route-type mix — a concrete, data-backed routing recommendation for this corridor tier.

## Run it yourself

```bash
pip install -r requirements.txt
python src/01_clean_data.py
python src/02_simulate_hub_policy.py
python src/03_sla_buffer_sweep.py
python src/04_make_charts.py
```

The raw dataset (`data/delhivery_india.csv`, ~55MB) is not committed to this repo; download it from the [source](https://www.kaggle.com/datasets/santanukundu/delhivery-dataset) and place it at that path before running `01_clean_data.py`.
