"""Step 3: read ALL test reports and show them in one table.

Each row is a test. Each column is a run.
    .   the test passed in that run
    F   the test failed in that run
    ?   the test was not in that run's report

The table is also saved as results_table.csv for the next steps.

How to run:   python read_all_reports.py
"""
import csv
import xml.etree.ElementTree as ET
from pathlib import Path

# 1. Find all the report files, in order: run_01.xml, run_02.xml, ...
here = Path(__file__).parent
folder = here / "sample_reports"
report_files = sorted(folder.glob("run_*.xml"))

if not report_files:
    print(f"No report files found in {folder}")
    raise SystemExit(1)

# 2. Read every report and fill the table.
# results["test_logout"] will become a list like [".", ".", "F", ...], one mark per run.
results = {}

for run_index, report_file in enumerate(report_files):
    suite = ET.parse(report_file).getroot()
    for test in suite.findall("testcase"):
        name = test.get("name")
        failed = test.find("failure") is not None or test.find("error") is not None
        if name not in results:
            results[name] = ["?"] * len(report_files)  # start with "not seen in this run"
        results[name][run_index] = "F" if failed else "."

# 3. Print the table.
print(f"Read {len(report_files)} reports from the folder {folder.name}")
print(".  = passed     F  = failed     ?  = test not in that report")
print()
print(f"{'test name':<35} runs 1 to {len(report_files)}")
for name, marks in results.items():
    print(f"{name:<35} {' '.join(marks)}")

# 4. Save the table as a CSV file (you can open it in Excel).
csv_path = here / "results_table.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["test_name"] + [report_file.stem for report_file in report_files])
    for name, marks in results.items():
        writer.writerow([name] + marks)

print()
print(f"Saved the table as {csv_path.name}")
