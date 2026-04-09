# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.8",
#   "pyyaml>=6.0",
# ]
# ///
"""Analyzer for the 10-step capsule sweep experiment.

All runners, no truncation. Incorrect steps shown as dotted lines.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from chart_helpers import (
    compute_ground_truth,
    extract_ops_per_runner,
    get_case_ids,
    load_analyzer_input,
    make_4_charts,
    write_output_json,
)


def main():
    inp = load_analyzer_input()
    exp = inp["experiment"]
    paths = inp["paths"]
    sessions = inp["sessions"]
    artifacts_dir = paths["artifacts_dir"]
    os.makedirs(artifacts_dir, exist_ok=True)

    case_ids = get_case_ids(sessions)
    if not case_ids:
        print("warning: no case data found", file=sys.stderr)
        write_output_json(paths["output_json"], [])
        return

    case_id = case_ids[0]
    runners_data = extract_ops_per_runner(sessions, case_id)
    ground_truth = compute_ground_truth(runners_data)

    title = exp.get("description") or exp["name"]
    chart_results = make_4_charts(
        runners_data, ground_truth, title, artifacts_dir,
        truncate=False, dash_incorrect=True,
    )

    artifacts = [
        {"kind": "image", "label": label, "path": path}
        for path, label in chart_results
    ]
    write_output_json(paths["output_json"], artifacts)


if __name__ == "__main__":
    main()
