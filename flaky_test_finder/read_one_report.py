"""Step 2: read ONE test report and print PASS or FAIL for every test.

How to run:   python read_one_report.py
Or pick a different report:   python read_one_report.py run_05.xml
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# 1. Find the report file.
report_name = sys.argv[1] if len(sys.argv) > 1 else "run_01.xml"
report_path = Path(__file__).parent / "sample_reports" / report_name

if not report_path.exists():
    print(f"Cannot find {report_path}")
    print("Check that the sample_reports folder is next to this file.")
    sys.exit(1)

# 2. Open the file and get the top of the "tree".
tree = ET.parse(report_path)
suite = tree.getroot()

# 3. Go through every test and decide PASS or FAIL.
print(f"Report: {report_name}")
test_count = 0
failed_count = 0
for test in suite.findall("testcase"):
    name = test.get("name")
    # Some tools write <error> instead of <failure>. We treat both as FAIL.
    # (Later we will also handle skipped tests.)
    if test.find("failure") is not None or test.find("error") is not None:
        result = "FAIL"
        failed_count += 1
    else:
        result = "PASS"
    test_count += 1
    print(f"{name:<35} {result}")

# 4. Print the total.
print(f"Total: {test_count} tests, {failed_count} failed")
