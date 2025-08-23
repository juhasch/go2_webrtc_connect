import argparse
import csv
import math
import os
from typing import Dict, List, Optional


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def load_samples(csv_path: str) -> Dict[str, List[float]]:
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        indices: List[int] = []
        robot_ts: List[float] = []
        local_ts: List[float] = []

        for row in reader:
            idx = _to_float(row.get("index"))
            rts = _to_float(row.get("robot_ts_s"))
            lts = _to_float(row.get("local_ts_s"))
            if rts is None or lts is None:
                continue
            indices.append(int(idx) if idx is not None else len(indices) + 1)
            robot_ts.append(rts)
            local_ts.append(lts)

    if not robot_ts:
        raise ValueError("CSV appears empty or missing required columns: robot_ts_s, local_ts_s")

    # Recompute derived metrics for consistency
    offsets: List[float] = [lt - rt for lt, rt in zip(local_ts, robot_ts)]
    initial_offset = offsets[0]
    drift_vs_initial: List[float] = [off - initial_offset for off in offsets]

    dt_robot: List[float] = [math.nan]
    dt_local: List[float] = [math.nan]
    for i in range(1, len(robot_ts)):
        dt_robot.append(robot_ts[i] - robot_ts[i - 1])
        dt_local.append(local_ts[i] - local_ts[i - 1])

    robot_t_rel = [rt - robot_ts[0] for rt in robot_ts]

    return {
        "index": indices,
        "robot_ts_s": robot_ts,
        "local_ts_s": local_ts,
        "robot_t_rel_s": robot_t_rel,
        "offset_s": offsets,
        "drift_vs_initial_s": drift_vs_initial,
        "dt_robot_s": dt_robot,
        "dt_local_s": dt_local,
    }


def _mean(values: List[float]) -> float:
    vals = [v for v in values if v == v]  # filter NaN
    return sum(vals) / len(vals) if vals else math.nan


def _stddev(values: List[float]) -> float:
    vals = [v for v in values if v == v]
    if len(vals) < 2:
        return math.nan
    m = _mean(vals)
    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    return math.sqrt(var)


def _min(values: List[float]) -> float:
    vals = [v for v in values if v == v]
    return min(vals) if vals else math.nan


def _max(values: List[float]) -> float:
    vals = [v for v in values if v == v]
    return max(vals) if vals else math.nan


def _linear_regression(x: List[float], y: List[float]) -> Optional[Dict[str, float]]:
    if len(x) != len(y) or len(x) < 2:
        return None
    n = float(len(x))
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xx = sum(v * v for v in x)
    sum_xy = sum(a * b for a, b in zip(x, y))
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return None
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return {"slope": slope, "intercept": intercept}


def summarize(data: Dict[str, List[float]]) -> str:
    offsets = data["offset_s"]
    drift = data["drift_vs_initial_s"]
    dt_robot = data["dt_robot_s"]
    dt_local = data["dt_local_s"]

    reg = _linear_regression(data["robot_ts_s"], data["local_ts_s"])
    drift_rate = (reg["slope"] - 1.0) if reg else math.nan
    drift_ppm = drift_rate * 1e6 if drift_rate == drift_rate else math.nan

    return (
        f"samples={len(offsets)} "
        f"offset_s: mean={_mean(offsets):.6f}, std={_stddev(offsets):.6f}, min={_min(offsets):.6f}, max={_max(offsets):.6f} | "
        f"dt_robot_s: mean={_mean(dt_robot):.3f}, std={_stddev(dt_robot):.3f} | "
        f"dt_local_s: mean={_mean(dt_local):.3f}, std={_stddev(dt_local):.3f} | "
        f"drift_rate={drift_rate:.9f} ({drift_ppm:.1f} ppm)"
    )


def plot_matplotlib(data: Dict[str, List[float]], outdir: str, prefix: str, show: bool) -> List[str]:
    # Use non-interactive backend if not showing plots
    if not show:
        import matplotlib
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(outdir, exist_ok=True)
    saved: List[str] = []

    # 1) Offset over index
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(data["index"], data["offset_s"], label="offset (local - robot)")
    mu = _mean(data["offset_s"]) if data["offset_s"] else 0.0
    ax.axhline(0.0, color="gray", linestyle="--", linewidth=1)
    ax.axhline(mu, color="orange", linestyle=":", linewidth=1, label=f"mean={mu:.6f}s")
    ax.set_title("Offset over samples")
    ax.set_xlabel("sample index")
    ax.set_ylabel("offset [s]")
    ax.legend()
    path = os.path.join(outdir, f"{prefix}_offset.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    saved.append(path)
    if show:
        plt.show()
    plt.close(fig)

    # 2) Drift vs initial
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(data["index"], data["drift_vs_initial_s"], label="drift vs initial offset")
    ax.axhline(0.0, color="gray", linestyle="--", linewidth=1)
    ax.set_title("Drift relative to initial offset")
    ax.set_xlabel("sample index")
    ax.set_ylabel("drift [s]")
    ax.legend()
    path = os.path.join(outdir, f"{prefix}_drift.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    saved.append(path)
    if show:
        plt.show()
    plt.close(fig)

    # 3) Interarrival times
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(data["index"], data["dt_robot_s"], label="robot dt")
    ax.plot(data["index"], data["dt_local_s"], label="local dt")
    ax.set_title("Interarrival times")
    ax.set_xlabel("sample index")
    ax.set_ylabel("seconds")
    ax.legend()
    path = os.path.join(outdir, f"{prefix}_interarrival.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    saved.append(path)
    if show:
        plt.show()
    plt.close(fig)

    # 4) Histogram of offsets
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist([v for v in data["offset_s"] if v == v], bins=60, color="#3b82f6")
    ax.set_title("Offset distribution")
    ax.set_xlabel("offset [s]")
    ax.set_ylabel("count")
    path = os.path.join(outdir, f"{prefix}_offset_hist.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    saved.append(path)
    if show:
        plt.show()
    plt.close(fig)

    return saved


def plot_altair(data: Dict[str, List[float]], outdir: str, prefix: str, show: bool) -> List[str]:
    try:
        import altair as alt
    except Exception as e:
        raise RuntimeError("Altair is not installed. Install with 'pip install altair'.") from e

    os.makedirs(outdir, exist_ok=True)
    records = [
        {
            "index": data["index"][i],
            "robot_t_rel_s": data["robot_t_rel_s"][i],
            "offset_s": data["offset_s"][i],
            "drift_vs_initial_s": data["drift_vs_initial_s"][i],
            "dt_robot_s": data["dt_robot_s"][i],
            "dt_local_s": data["dt_local_s"][i],
        }
        for i in range(len(data["index"]))
    ]

    charts = []
    # Offset over index
    charts.append(
        alt.Chart(records).mark_line().encode(x="index:Q", y="offset_s:Q").properties(title="Offset over samples", width=800, height=250)
    )
    # Drift vs initial
    charts.append(
        alt.Chart(records).mark_line().encode(x="index:Q", y="drift_vs_initial_s:Q").properties(title="Drift vs initial", width=800, height=250)
    )
    # Interarrival times
    interarrival = alt.layer(
        alt.Chart(records).mark_line(color="#1f77b4").encode(x="index:Q", y="dt_robot_s:Q"),
        alt.Chart(records).mark_line(color="#ff7f0e").encode(x="index:Q", y="dt_local_s:Q"),
    ).properties(title="Interarrival times", width=800, height=250)
    charts.append(interarrival)
    # Histogram of offsets
    hist = alt.Chart(records).mark_bar().encode(
        alt.X("offset_s:Q", bin=alt.Bin(maxbins=60)),
        y="count()"
    ).properties(title="Offset distribution", width=800, height=250)
    charts.append(hist)

    combined = alt.vconcat(*charts)
    html_path = os.path.join(outdir, f"{prefix}_report.html")
    combined.save(html_path)

    if show:
        # Altair doesn't provide a built-in viewer; print path for manual open
        print(f"Open HTML report: {html_path}")

    return [html_path]


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze timestamp drift CSV and visualize results")
    parser.add_argument("csv", type=str, help="Path to CSV produced by timestamp_drift.py")
    parser.add_argument("--backend", choices=["matplotlib", "altair"], default="matplotlib", help="Visualization backend")
    parser.add_argument("--outdir", type=str, default=None, help="Directory to save outputs (default: alongside CSV)")
    parser.add_argument("--prefix", type=str, default=None, help="Filename prefix (default: CSV stem)")
    parser.add_argument("--show", action="store_true", help="Display plots interactively (matplotlib) or print HTML path (altair)")
    args = parser.parse_args()

    data = load_samples(args.csv)

    # Output paths
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.csv))
    prefix = args.prefix or os.path.splitext(os.path.basename(args.csv))[0]

    # Print concise summary
    print(summarize(data))

    # Generate visuals
    if args.backend == "matplotlib":
        paths = plot_matplotlib(data, outdir=outdir, prefix=prefix, show=args.show)
    else:
        paths = plot_altair(data, outdir=outdir, prefix=prefix, show=args.show)

    # Minimal status line with saved files
    if paths:
        print("Saved:")
        for p in paths:
            print(f"- {p}")


if __name__ == "__main__":
    main()


