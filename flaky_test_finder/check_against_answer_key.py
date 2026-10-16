"""Step 7: check the tool against the answer key.

The answer key (answer_key.txt) was written when we made the practice reports.
It says what every test REALLY is. Here we run the finder and compare.

How to run:   python check_against_answer_key.py
"""
from pathlib import Path

from flaky_test_finder import read_reports, sort_tests

here = Path(__file__).parent
key_path = here / "answer_key.txt"
if not key_path.exists():
    print("Cannot find answer_key.txt. Run make_sample_reports.py first (step 1).")
    raise SystemExit(1)

# 1. Read the true answers. Test lines start with "test_" and end with the true label.
true_label = {}
for line in key_path.read_text(encoding="utf-8").splitlines():
    if line.startswith("test_"):
        words = line.split()
        last_word = words[-1]            # "FLAKY", "healthy", or "not flaky)" for the broken test
        if last_word == "FLAKY":
            true_label[words[0]] = "FLAKY"
        elif last_word == "healthy":
            true_label[words[0]] = "HEALTHY"
        else:
            true_label[words[0]] = "BROKEN"

# 2. Run the finder on the sample reports and note what it said.
table, report_files, commits, unreadable = read_reports(here / "sample_reports")
flaky, broken, healthy, _ = sort_tests(table)
found_label = {}
for group, label in ((flaky, "FLAKY"), (broken, "BROKEN"), (healthy, "HEALTHY")):
    for rate, test_id, fails, runs_seen in group:
        found_label[test_id.split(".")[-1]] = label  # cut off the class name

# 3. Compare.
print(f"{'test name':<35} {'truth':<9} {'tool said':<9} result")
right = 0
missed = []
for name, truth in true_label.items():
    said = found_label.get(name, "not seen")
    if said == truth:
        result = "right"
        right += 1
    else:
        result = "MISSED"
        missed.append(name)
    print(f"{name:<35} {truth:<9} {said:<9} {result}")

print()
print(f"The tool was right for {right} of {len(true_label)} tests.")
for name in missed:
    print(f"Missed: {name} (truth {true_label[name]}, tool said {found_label.get(name)})")
if missed:
    print("A missed flaky test is not a bug. It failed 0 times in 20 runs, so the tool had nothing to see.")
