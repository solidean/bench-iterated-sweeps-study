#!/usr/bin/env python3
"""Generate swept-capsules-1000.case with sweep_0000 through sweep_1000."""

header = """\
+++
name: Iterated Swept Difference (1000 Steps)
date: 2026-03-16
schema: 1
format: simple
comment: Iteratively subtract 1000 sweep steps from a workpiece. Each boolean-difference feeds into the next, simulating a swept machining operation.
requires:
  - booleans
+++"""

lines = [header, 'w = load-mesh "workpiece.obj"']
for i in range(1001):
    lines.append(f'w = boolean-difference w "sweeps/sweep_{i:04d}.obj"')

output = "\n".join(lines) + "\n"

with open("swept-capsules-1000.case", "w") as f:
    f.write(output)

print(f"Written {1001} sweep steps (sweep_0000 through sweep_1000).")
