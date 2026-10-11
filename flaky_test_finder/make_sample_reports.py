"""Step 1: make practice test reports for the Flaky Test Finder.

Real test tools (JUnit, pytest, Selenium and others) write a small XML file
after every test run. This script writes 20 such files ("runs") for 12
made-up tests. All 20 runs are on the SAME code, so any test that both passes
and fails is flaky.

Some tests are flaky ON PURPOSE, so that later we can check that our tool finds
them. The answer is saved in answer_key.txt.

NOTE: this is practice data made up by a program. It is not real test data.

How to run:   python make_sample_reports.py
"""
import random
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

NUMBER_OF_RUNS = 20
SEED = 7  # the same seed gives the same files every time

# Each line: class name, test name, chance of failing in ONE run, failure message
#   0.00        -> always passes (a healthy test)
#   0.02 - 0.40 -> flaky: fails some of the time, passes the rest
#   1.00        -> always fails (a broken test, NOT flaky)
TESTS = [
    ("shop.LoginTests", "test_login_valid_user", 0.00, ""),
    ("shop.LoginTests", "test_login_wrong_password", 0.00, ""),
    ("shop.LoginTests", "test_logout", 0.00, ""),
    ("shop.LoginTests", "test_login_after_session_timeout", 0.25,
     "TimeoutError: login button not found after 10 seconds"),
    ("shop.SearchTests", "test_search_by_name", 0.00, ""),
    ("shop.SearchTests", "test_search_empty_query", 0.00, ""),
    ("shop.SearchTests", "test_search_filters", 0.00, ""),
    ("shop.SearchTests", "test_search_autocomplete", 0.08,
     "AssertionError: expected 5 suggestions but found 0"),
    ("shop.CheckoutTests", "test_add_to_cart", 0.00, ""),
    ("shop.CheckoutTests", "test_pay_by_card", 0.40,
     "TimeoutError: payment page did not load"),
    ("shop.CheckoutTests", "test_apply_coupon", 0.02,
     "AssertionError: expected total 45.00 but was 50.00"),
    ("shop.CheckoutTests", "test_invoice_download", 1.00,
     "AssertionError: invoice PDF is empty"),
]


def write_one_run(run_number, rng, folder):
    """Write one XML report and return the names of the tests that failed."""
    started = datetime(2026, 10, 1, 10, 0) + timedelta(minutes=30 * (run_number - 1))
    lines = []
    failed_tests = []
    total_seconds = 0.0

    for class_name, test_name, fail_chance, message in TESTS:
        seconds = round(rng.uniform(0.1, 2.0), 2)
        total_seconds += seconds
        if rng.random() < fail_chance:
            failed_tests.append(test_name)
            error_type = message.split(":")[0]
            lines.append(
                f'    <testcase classname="{class_name}" name="{test_name}" time="{seconds}">\n'
                f'      <failure message={quoteattr(message)} type="{error_type}">{escape(message)}</failure>\n'
                f'    </testcase>'
            )
        else:
            lines.append(f'    <testcase classname="{class_name}" name="{test_name}" time="{seconds}"/>')

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="shop-tests" tests="{len(TESTS)}" failures="{len(failed_tests)}" '
        f'errors="0" skipped="0" time="{round(total_seconds, 2)}" '
        f'timestamp="{started.isoformat()}">\n'
        '  <properties>\n'
        '    <property name="commit" value="a1b2c3d"/>\n'  # same code in every run
        '  </properties>\n'
        + "\n".join(lines)
        + '\n</testsuite>\n'
    )
    (folder / f"run_{run_number:02d}.xml").write_text(xml, encoding="utf-8")
    return failed_tests


def main():
    here = Path(__file__).parent
    folder = here / "sample_reports"
    folder.mkdir(exist_ok=True)
    rng = random.Random(SEED)

    fail_counts = {test_name: 0 for _, test_name, _, _ in TESTS}
    for run_number in range(1, NUMBER_OF_RUNS + 1):
        for test_name in write_one_run(run_number, rng, folder):
            fail_counts[test_name] += 1

    # Answer key: what we planted, and what actually happened in these 20 runs.
    key = ["ANSWER KEY (practice data made up by make_sample_reports.py)", "",
           f"{NUMBER_OF_RUNS} runs, all on the same commit (a1b2c3d).", "",
           "test name                           planned chance   failed in these runs   what it is"]
    for _, test_name, chance, _ in TESTS:
        if chance == 0:
            kind = "healthy"
        elif chance == 1:
            kind = "BROKEN (always fails, not flaky)"
        else:
            kind = "FLAKY"
        key.append(f"{test_name:<35} {chance:>13.0%}   {fail_counts[test_name]:>10} of {NUMBER_OF_RUNS}"
                   f"          {kind}")
    key += ["", "A flaky test with a small failure chance can pass in every run just by luck.",
            "That is why a tool needs many runs before it can judge a test."]
    (here / "answer_key.txt").write_text("\n".join(key) + "\n", encoding="utf-8")

    print(f"Wrote {NUMBER_OF_RUNS} reports to {folder}")
    print("\n".join(key))


if __name__ == "__main__":
    main()
