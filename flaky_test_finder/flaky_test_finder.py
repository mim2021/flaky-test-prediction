"""Flaky Test Finder (step 6): one program that does steps 2 to 5.

Point it at a folder of test reports. Each XML file must be ONE complete test
run (JUnit XML format) of the SAME code. The program finds the flaky tests,
ranks them, gives advice, and saves flaky_report.csv and flaky_report.txt.

How to run:
    python flaky_test_finder.py                      (uses the sample_reports folder)
    python flaky_test_finder.py C:\\path\\to\\reports   (uses your own folder)
"""
import argparse
import csv
import math
import xml.etree.ElementTree as ET
from pathlib import Path

# ---- Settings you can change ----
FIX_FIRST_RATE = 0.20  # a flaky test that fails in 20% of runs or more is "FIX FIRST"
CONFIDENCE = 0.95      # "sure" means 95% sure
EXAMPLE_RATE = 0.02    # used in the warning: runs needed to see a test that fails 2% of the time
# ---------------------------------


def read_reports(folder):
    """Read every XML report in the folder (each file = one run).

    Returns the table, the list of report files, the commits found, and the
    names of files that could not be read.
    """
    report_files = sorted(folder.glob("*.xml"))
    table = {}        # test id -> one mark per run: "." passed, "F" failed, "?" not seen
    commits = set()
    unreadable = []

    for run_index, report_file in enumerate(report_files):
        try:
            root = ET.parse(report_file).getroot()
        except ET.ParseError:
            unreadable.append(report_file.name)
            continue

        for prop in root.iter("property"):
            if prop.get("name") == "commit":
                commits.add(prop.get("value"))

        for test in root.iter("testcase"):
            class_name = test.get("classname")
            test_id = f"{class_name}.{test.get('name')}" if class_name else test.get("name")
            if test.find("skipped") is not None:
                continue  # a skipped test did not really run, so it counts as "not seen"
            failed = test.find("failure") is not None or test.find("error") is not None
            if test_id not in table:
                table[test_id] = ["?"] * len(report_files)
            table[test_id][run_index] = "F" if failed else "."

    return table, report_files, commits, unreadable


def sort_tests(table):
    """Put every test in one group: flaky, broken or healthy."""
    flaky, broken, healthy = [], [], []
    fewest_runs = None  # the smallest number of runs any test was seen in

    for test_id, marks in table.items():
        passes = marks.count(".")
        fails = marks.count("F")
        runs_seen = passes + fails
        if runs_seen == 0:
            continue
        if fewest_runs is None or runs_seen < fewest_runs:
            fewest_runs = runs_seen

        item = (fails / runs_seen, test_id, fails, runs_seen)  # (failure rate, name, fails, runs)
        if fails == 0:
            healthy.append(item)
        elif passes == 0:
            broken.append(item)
        else:
            flaky.append(item)

    flaky.sort(reverse=True)  # highest failure rate first
    broken.sort()
    healthy.sort()
    return flaky, broken, healthy, fewest_runs


def reruns_needed(rate):
    """How many reruns until we are CONFIDENCE sure of seeing at least one failure."""
    return math.ceil(math.log(1 - CONFIDENCE) / math.log(1 - rate))


def build_summary(folder, report_files, commits, unreadable, flaky, broken, healthy, fewest_runs):
    """Build the text summary as a list of lines."""
    names = [item[1] for item in flaky + broken + healthy]
    width = max(len(name) for name in names)
    lines = []

    lines.append(f"Read {len(report_files) - len(unreadable)} reports from {folder}")
    if unreadable:
        lines.append(f"WARNING: could not read {len(unreadable)} file(s): {', '.join(unreadable)}")
    if len(commits) > 1:
        lines.append(f"WARNING: the reports come from {len(commits)} different commits. A flaky test is one that")
        lines.append("gives different results on the SAME code, so use runs of one commit only.")
    elif not commits:
        lines.append("Note: no commit information found. Make sure all runs are of the same code.")
    lines.append(f"Reruns = how many reruns make you {CONFIDENCE:.0%} sure of seeing at least one failure.")
    lines.append("")

    lines.append("FLAKY TESTS (worst first)")
    if not flaky:
        lines.append("  none found")
    for rate, name, fails, runs_seen in flaky:
        action = "FIX FIRST" if rate >= FIX_FIRST_RATE else "WATCH"
        lines.append(f"  {action:<10} {name:<{width}}  fails in {rate:.0%} of runs ({fails} of {runs_seen})"
                     f"   reruns: about {reruns_needed(rate)}")

    lines.append("")
    lines.append("BROKEN TESTS (they always fail, so they are not flaky)")
    if not broken:
        lines.append("  none found")
    for rate, name, fails, runs_seen in broken:
        lines.append(f"  {'FIX':<10} {name:<{width}}  failed {fails} of {runs_seen} runs")

    lines.append("")
    lines.append(f"HEALTHY TESTS: {len(healthy)} (no failure seen in these runs)")

    hidden_rate = 1 - (1 - CONFIDENCE) ** (1 / fewest_runs)
    lines.append("")
    lines.append(f"WARNING: tests were seen in as few as {fewest_runs} runs. A flaky test that fails in")
    lines.append(f"less than about {hidden_rate:.0%} of runs can still look healthy. For example, to be {CONFIDENCE:.0%} sure")
    lines.append(f"of seeing a test that fails in {EXAMPLE_RATE:.0%} of runs, you need about {reruns_needed(EXAMPLE_RATE)} runs.")
    lines.append("The failure rates above come from few runs, so treat them as rough.")
    return lines


def write_csv(path, flaky, broken, healthy):
    """Save every test in a CSV file that opens in Excel."""
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["test", "label", "action", "failed_runs", "runs_seen",
                         "failure_rate", f"reruns_for_{CONFIDENCE:.0%}_sure"])
        for rate, name, fails, runs_seen in flaky:
            action = "FIX FIRST" if rate >= FIX_FIRST_RATE else "WATCH"
            writer.writerow([name, "FLAKY", action, fails, runs_seen, f"{rate:.0%}", reruns_needed(rate)])
        for rate, name, fails, runs_seen in broken:
            writer.writerow([name, "BROKEN", "FIX", fails, runs_seen, f"{rate:.0%}", ""])
        for rate, name, fails, runs_seen in healthy:
            writer.writerow([name, "HEALTHY", "NO ACTION", fails, runs_seen, f"{rate:.0%}", ""])


def main():
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Find flaky tests in a folder of JUnit XML reports.")
    parser.add_argument("folder", nargs="?", default=str(here / "sample_reports"),
                        help="folder with the XML reports (default: the sample_reports folder)")
    parser.add_argument("--out", default=str(here),
                        help="folder for flaky_report.csv and flaky_report.txt (default: next to this program)")
    args = parser.parse_args()

    folder = Path(args.folder)
    out_folder = Path(args.out)

    if not folder.is_dir():
        print(f"Cannot find the folder {folder}")
        raise SystemExit(1)

    table, report_files, commits, unreadable = read_reports(folder)
    if not report_files:
        print(f"No .xml report files found in {folder}")
        raise SystemExit(1)

    flaky, broken, healthy, fewest_runs = sort_tests(table)
    if fewest_runs is None:
        print("The reports contain no test results.")
        raise SystemExit(1)

    summary = build_summary(folder, report_files, commits, unreadable, flaky, broken, healthy, fewest_runs)
    print("\n".join(summary))

    out_folder.mkdir(parents=True, exist_ok=True)
    write_csv(out_folder / "flaky_report.csv", flaky, broken, healthy)
    (out_folder / "flaky_report.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print()
    print(f"Saved flaky_report.csv and flaky_report.txt in {out_folder}")


if __name__ == "__main__":
    main()
