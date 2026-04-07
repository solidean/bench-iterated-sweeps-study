"""Shared helpers for iterated-sweep analyzer scripts."""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_analyzer_input():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <analyzer_input.json>", file=sys.stderr)
        sys.exit(1)
    return load_json(sys.argv[1])


def write_output_json(path, artifacts):
    out = {"status": "ok", "artifacts": artifacts}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# Runner data extraction
# ---------------------------------------------------------------------------

def _load_runner_color(runner_yaml_path):
    """Extract the first variant color from a runner.yaml file."""
    try:
        with open(runner_yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for v in (data.get("variants") or {}).values():
            color = v.get("color")
            if color:
                return color
    except Exception:
        pass
    return None


def extract_ops_per_runner(sessions, case_id):
    """Return [(display_name, slug, ops, color)] for a given case_id.

    Uses the first session that has data for each runner.
    """
    seen = set()
    results = []

    for session in sessions:
        for slug, runner_data in session["runners"].items():
            if slug in seen:
                continue
            result_path = runner_data.get("cases", {}).get(case_id)
            if not result_path:
                continue
            result = load_json(result_path)
            name = result.get("runner_name") or result.get("runner_variant", slug)
            color = _load_runner_color(runner_data["runner_yaml"])
            results.append((name, slug, result.get("ops", []), color))
            seen.add(slug)

    results.sort(key=lambda r: r[0])
    return results


def get_case_ids(sessions):
    """Return all case IDs present in the sessions data."""
    ids = set()
    for session in sessions:
        for runner_data in session["runners"].values():
            ids.update(runner_data.get("cases", {}).keys())
    return sorted(ids)


# ---------------------------------------------------------------------------
# Correctness logic
# ---------------------------------------------------------------------------

def is_known_good(runner_name):
    n = runner_name.lower()
    return "solidean" in n or "cgal nef" in n


def compute_ground_truth(all_runner_ops):
    """Compute per-step ground truth from known-good runners.

    Returns {step_idx: {"volumes": [...], "areas": [...]}}.
    """
    gt = {}
    for name, _slug, ops, _color in all_runner_ops:
        if not is_known_good(name):
            continue
        for i, op in enumerate(ops):
            if op.get("status") != "success":
                continue
            stats = op.get("out_stats")
            if not stats:
                continue
            entry = gt.setdefault(i, {"volumes": [], "areas": []})
            entry["volumes"].append(stats.get("volume", 0.0))
            entry["areas"].append(stats.get("area", 0.0))
    return gt


def is_step_correct(op, step_idx, ground_truth):
    """A step is correct if status==success, defect==0, and area/volume
    are within 10% of any known-good reference value."""
    if op.get("status") != "success":
        return False
    stats = op.get("out_stats")
    if not stats:
        return False
    if stats.get("total_defect", 0) != 0:
        return False

    ref = ground_truth.get(step_idx)
    if not ref:
        return True  # no reference available, assume OK

    def within_10(actual, candidates):
        if not candidates:
            return True
        return any(
            abs(actual - c) / max(abs(c), 1e-12) <= 0.10
            for c in candidates
        )

    if not within_10(stats.get("volume", 0.0), ref["volumes"]):
        return False
    if not within_10(stats.get("area", 0.0), ref["areas"]):
        return False
    return True


def find_truncation_point(ops, ground_truth):
    """Return the index of the first incorrect step, or len(ops)."""
    for i, op in enumerate(ops):
        if not is_step_correct(op, i, ground_truth):
            return i
    return len(ops)


# ---------------------------------------------------------------------------
# Metric extractors
# ---------------------------------------------------------------------------

def timing_fn(op):
    if op.get("status") != "success":
        return None
    return op.get("operation_ms", 0) + op.get("import_ms", 0)


def area_fn(op):
    if op.get("status") != "success":
        return None
    stats = op.get("out_stats")
    return stats.get("area") if stats else None


def volume_fn(op):
    if op.get("status") != "success":
        return None
    stats = op.get("out_stats")
    return stats.get("volume") if stats else None


def triangles_fn(op):
    if op.get("status") != "success":
        return None
    stats = op.get("out_stats")
    return stats.get("tri_count") if stats else None


METRICS = [
    ("timing",    "Time (ms)",  timing_fn,    True),
    ("area",      "Area",       area_fn,      False),
    ("volume",    "Volume",     volume_fn,    False),
    ("triangles", "Triangles",  triangles_fn, True),
]


# ---------------------------------------------------------------------------
# Charting
# ---------------------------------------------------------------------------

def plot_metric(ax, runners_data, metric_fn, ground_truth,
                truncate=False, dash_incorrect=False, log_scale=False):
    """Plot one metric onto an axes.

    runners_data: [(name, slug, ops, color)]
    """
    for name, _slug, ops, color in runners_data:
        steps = []
        values = []
        trunc = find_truncation_point(ops, ground_truth) if truncate else len(ops)

        for i, op in enumerate(ops):
            if i >= trunc:
                break
            val = metric_fn(op)
            if val is None:
                continue
            steps.append(i + 1)
            values.append(val)

        if not steps:
            continue

        kwargs = dict(label=name, linewidth=1.5)
        if color:
            kwargs["color"] = color

        if dash_incorrect:
            # split into correct/incorrect segments
            correct_s, correct_v = [], []
            incorrect_s, incorrect_v = [], []
            for s, v, op in zip(steps, values, ops):
                if is_step_correct(op, s - 1, ground_truth):
                    # bridge from last incorrect point if needed
                    if incorrect_s:
                        correct_s.append(s)
                        correct_v.append(v)
                    correct_s.append(s)
                    correct_v.append(v)
                    if incorrect_s:
                        # flush incorrect segment
                        ax.plot(incorrect_s, incorrect_v, linestyle=":",
                                alpha=0.5, linewidth=1.2,
                                color=color if color else None)
                        incorrect_s, incorrect_v = [], []
                else:
                    if correct_s:
                        # bridge from last correct point
                        incorrect_s.append(correct_s[-1])
                        incorrect_v.append(correct_v[-1])
                    incorrect_s.append(s)
                    incorrect_v.append(v)

            if correct_s:
                ax.plot(correct_s, correct_v, **kwargs)
                kwargs.pop("label", None)  # only label once
            if incorrect_s:
                kwargs.pop("label", None)
                ax.plot(incorrect_s, incorrect_v, linestyle=":",
                        alpha=0.5, linewidth=1.2,
                        color=color if color else None)
        else:
            ax.plot(steps, values, **kwargs)

            # mark termination if truncated before end
            if truncate and trunc < len(ops) and steps:
                ax.plot(steps[-1], values[-1], marker="x", markersize=8,
                        color=color if color else "red")

    if log_scale:
        ax.set_yscale("log")
    ax.set_xlabel("Step")
    ax.legend(fontsize="small", loc="best")
    ax.grid(True, alpha=0.3)


def make_4_charts(runners_data, ground_truth, title_prefix, artifacts_dir,
                  truncate=False, dash_incorrect=False):
    """Create 4 SVG charts (timing, area, volume, triangles).

    Returns list of (filename, label) tuples for artifacts.
    """
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for metric_id, ylabel, fn, log_scale in METRICS:
        fig, ax = plt.subplots(figsize=(12, 6))
        title = f"{title_prefix} \u2014 {ylabel}"
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        plot_metric(ax, runners_data, fn, ground_truth,
                    truncate=truncate, dash_incorrect=dash_incorrect,
                    log_scale=log_scale)
        fig.tight_layout()

        filename = f"{metric_id}.svg"
        path = artifacts_dir / filename
        fig.savefig(str(path), format="svg", bbox_inches="tight")
        plt.close(fig)
        print(f"  wrote {path}")
        results.append((str(path), f"{title_prefix} {ylabel}"))

    return results
