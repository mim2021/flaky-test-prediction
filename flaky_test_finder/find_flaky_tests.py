"""Step 4: find the flaky tests.

Reads results_table.csv (made in step 3) and gives every test a label:
    FLAKY    it passed in some runs and failed in others
    BROKEN   it failed in every run it was in (not flaky, just broken)
    HEALTHY  no failure seen in these runs

How to run:   python find_flaky_tests.py
"""
import csv
from pathlib import Path

csv_path = Path(__file__).parent / "results_table.csv"

if not csv_path.exists():
    print("Cannot find results_table.csv. Run read_all_reports.py first (step 3).")
    raise SystemExit(1)

# 1. Read the table. The first row is the header, the other rows are the tests.
with open(csv_path, newline="", encoding="utf-8") as file:
    rows = list(csv.reader(file))
test_rows = rows[1:]

# 2. Count passes and fails for every test, and give it a label.
label_order = {"FLAKY": 0, "BROKEN": 1, "HEALTHY": 2}  # the order we want in the printout
tests = []
for row in test_rows:
    name = row[0]
    marks = row[1:]
    passes = marks.count(".")
    fails = marks.count("F")
    runs_seen = passes + fails  # the "?" marks are not counted
    if runs_seen == 0:
        continue  # this test was never seen, so there is nothing to judge

    failure_rate = fails / runs_seen
    if fails == 0:
        label = "HEALTHY"
    elif passes == 0:
        label = "BROKEN"
    else:
        label = "FLAKY"

    # Python sorts these tuples by the first item, then the second, and so on.
    # The minus sign puts the highest failure rate first.
    tests.append((label_order[label], -failure_rate, name, label, fails, runs_seen))

tests.sort()

# 3. Print the result.
print("FLAKY = passed and failed     BROKEN = always fails     HEALTHY = no failure seen in these runs")
print()
counts = {"FLAKY": 0, "BROKEN": 0, "HEALTHY": 0}
for _, _, name, label, fails, runs_seen in tests:
    counts[label] += 1
    percent = fails / runs_seen
    print(f"{label:<9}{name:<35} failed {fails} of {runs_seen:<3} ({percent:.0%})")

print()
print(f"Found: {counts['FLAKY']} flaky, {counts['BROKEN']} broken, {counts['HEALTHY']} healthy")
