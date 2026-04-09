# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.8",
#   "pyyaml>=6.0",
# ]
# ///
"""Summary analyzer — generates a markdown report referencing all experiment charts."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from chart_helpers import load_analyzer_input, write_output_json

EXPERIMENT_DESCRIPTIONS = {
    "swept-capsules-10": (
        "10-step capsule sweep with all runners. "
        "Incorrect steps are shown as dotted lines but lines are not truncated, "
        "giving a full picture of each runner's behavior across all steps."
    ),
    "swept-capsules-100": (
        "100-step capsule sweep with all runners. "
        "Lines are truncated at the first incorrect step (defect > 0 or "
        ">10% deviation from ground truth), showing how far each runner "
        "can go before producing incorrect results."
    ),
    "swept-cylinders-267": (
        "267-step cylinder sweep with selected runners (CGAL, Solidean, "
        "Manifold, Trueform). Same truncation logic as the 100-step experiment."
    ),
    "swept-capsules-1000": (
        "1000-step capsule sweep with selected runners (CGAL, Solidean, "
        "Manifold, Trueform). Same truncation logic as the 100-step experiment."
    ),
}


def main():
    inp = load_analyzer_input()
    paths = inp["paths"]
    config = inp["experiment"].get("config") or {}
    siblings = config.get("sibling_experiments", [])
    artifacts_dir = Path(paths["artifacts_dir"])
    os.makedirs(artifacts_dir, exist_ok=True)

    # Resolve sibling experiment artifact directories.
    # work_dir is .materialized/<suite>/experiments/<this_exp>/
    # siblings are at .materialized/<suite>/experiments/<sibling>/artifacts/
    work_dir = Path(paths["work_dir"])
    experiments_parent = work_dir.parent

    lines = []
    lines.append("# Iterated Sweep Study Report")
    lines.append("")
    lines.append("This report summarizes the results of all iterated sweep experiments.")
    lines.append("Each experiment tests boolean-difference operations applied iteratively,")
    lines.append("simulating swept machining toolpaths of increasing complexity.")
    lines.append("")

    for exp_name in siblings:
        sibling_artifacts = experiments_parent / exp_name / "artifacts"

        lines.append(f"## {exp_name}")
        lines.append("")
        desc = EXPERIMENT_DESCRIPTIONS.get(exp_name, "")
        if desc:
            lines.append(desc)
            lines.append("")

        if sibling_artifacts.is_dir():
            svgs = sorted(sibling_artifacts.glob("*.svg"))
            if svgs:
                for svg in svgs:
                    label = svg.stem.replace("-", " ").replace("_", " ").title()
                    lines.append(f"### {label}")
                    lines.append("")
                    lines.append(f"![{label}]({svg})")
                    lines.append("")
            else:
                lines.append("*No charts found for this experiment.*")
                lines.append("")
        else:
            lines.append("*Artifacts not yet generated. Run the experiment first.*")
            lines.append("")

    md_path = artifacts_dir / "summary.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {md_path}")

    artifacts = [
        {"kind": "markdown", "label": "Iterated Sweep Study Report", "path": str(md_path)}
    ]
    write_output_json(paths["output_json"], artifacts)


if __name__ == "__main__":
    main()
