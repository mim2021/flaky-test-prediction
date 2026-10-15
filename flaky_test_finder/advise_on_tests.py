"""Step 5: rank the tests and give advice.

Reads results_table.csv (made in step 3), counts passes and fails (like step 4),
and then tells you what to do about every test that is not healthy.

How to run:   python advise_on_tests.py
"""
import csv
import math
from pathlib import Path

# ---- Settings you can change ----
FIX_FIRST_RATE = 0.20  # a flaky test that fails in 20% of runs or more is "FIX FIRST"
CONFIDENCE = 0.95      # "sure" means 95% sure
EXAMPLE_RATE = 0.02    # used in the warning: how many runs to see a test that fails 2% of the time
# ---------------------------------

csv_path = Path(__file__).parent / "results_table.csv"

if not csv_path.exists():
    print("Cannot find results_table.csv. Run read_all_reports.py first (step 3).")
    raise SystemExit(1)

# 1. Read the table.
with open(csv_path, newline="", encoding="utf-8") as file:
    rows = list(csv.reader(file))

# 2. Sort the tests into three groups (same counting as step 4).
flaky = []   # each item: (failure rate, name, fails, runs seen)
broken = []
healthy_count = 0
fewest_runs = None  # the smallest number of runs any test was seen in

for row in rows[1:]:
    name = row[0]
    marks = row[1:]
    passes = marks.count(".")
    fails = marks.count("F")
    runs_seen = passes + fails
    if runs_seen == 0:
        continue
    if fewest_runs is None or runs_seen < fewest_runs:
        fewest_runs = runs_seen

    rate = fails / runs_seen
    if fails == 0:
        healthy_count += 1
    elif passes == 0:
        broken.append((rate, name, fails, runs_seen))
    else:
        flaky.append((rate, name, fails, runs_seen))

if fewest_runs is None:
    print("The table has no test results.")
    raise SystemExit(1)

flaky.sort(reverse=True)  # reverse=True puts the highest failure rate first


def reruns_needed(rate):
    """How many reruns until we are CONFIDENCE sure of seeing at least one failure."""
    return math.ceil(math.log(1 - CONFIDENCE) / math.log(1 - rate))


# 3. Print the advice.
print(f"Reruns = how many reruns make you {CONFIDENCE:.0%} sure of seeing at least one failure.")
print()

print("FLAKY TESTS (worst first)")
if not flaky:
    print("  none found")
for rate, name, fails, runs_seen in flaky:
    action = "FIX FIRST" if rate >= FIX_FIRST_RATE else "WATCH"
    print(f"  {action:<10} {name:<35} fails in {rate:.0%} of runs ({fails} of {runs_seen})"
          f"   reruns: about {reruns_needed(rate)}")

print()
print("BROKEN TESTS (they always fail, so they are not flaky)")
if not broken:
    print("  none found")
for rate, name, fails, runs_seen in broken:
    print(f"  {'FIX':<10} {name:<35} failed {fails} of {runs_seen} runs")

print()
print(f"HEALTHY TESTS: {healthy_count} (no failure seen in these runs)")

# 4. The warning: how rare can a flaky test be and still look healthy?
hidden_rate = 1 - (1 - CONFIDENCE) ** (1 / fewest_runs)
runs_for_example = reruns_needed(EXAMPLE_RATE)
print()
print(f"WARNING: tests were seen in as few as {fewest_runs} runs. A flaky test that fails in")
print(f"less than about {hidden_rate:.0%} of runs can still look healthy. For example, to be {CONFIDENCE:.0%} sure")
print(f"of seeing a test that fails in {EXAMPLE_RATE:.0%} of runs, you need about {runs_for_example} runs.")
print("The failure rates above come from few runs, so treat them as rough.")
