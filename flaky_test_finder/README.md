# Flaky Test Finder

A small Python tool that reads test reports from many runs of the same code, finds the flaky tests, and tells you how many reruns you need before you can trust the answer. It runs from the command line, and it also has a web page with charts.

By Jannatul Ferdus Mim

## Why I built this

I work in test automation, and flaky tests are a known headache in this field. A flaky test passes on one run and fails on the next, even though the code did not change. When a build goes red, nobody knows if it is a real bug or just noise. People rerun the build, lose time, and slowly stop trusting the tests.

I wanted a simple way to answer two questions from the reports I already have:

1. Which tests are flaky, and which should I fix first?
2. If a test looks fine, how sure can I be?

The second question is the one I care about most. A test that fails only 2% of the time will look healthy in most small sets of runs. Many tools rerun a failed test and stop there. I wanted the tool to say how many runs are enough, and to say clearly when it cannot know.

## What it does

You give it a folder of JUnit XML reports. Each file must be one full run of the same code. The tool then:

- puts every test into one table (tests down the side, runs across the top)
- labels each test as flaky (passed and failed), broken (always fails) or healthy (never failed)
- ranks the flaky tests by failure rate. Tests that fail in 20% of runs or more are marked FIX FIRST, the others WATCH
- tells you how many reruns would make you 95% sure of seeing a failure
- warns you about the tests it cannot judge, because a rare flaky test can look healthy
- warns you if the reports come from different commits, since a flaky test has to be judged on the same code
- saves the result as `flaky_report.csv` (opens in Excel) and `flaky_report.txt`

The rerun number comes from simple probability. If a test fails with chance p in each run, the chance of seeing at least one failure in k runs is 1 - (1 - p)^k. So for 95% you need k = ceil(ln 0.05 / ln(1 - p)). A test that fails 5% of the time needs about 59 runs.

The same idea gives the warning. With 20 runs, a flaky test that fails in less than about 14% of runs can still look healthy. To be 95% sure of catching a test that fails 2% of the time, you need about 149 runs.

There is no machine learning in this tool. It only counts and does basic probability, so every number can be checked by hand. I did this on purpose.

## The web page

The command line works, but I also wanted people to be able to pick their files with a click. So I built a web page.

![The Flaky Test Finder web page](web_page.png)

You choose a folder of reports and press "Find flaky tests". Then the page shows you:

- a short summary and the warnings, for example when the reports come from different commits
- a donut chart with the number of flaky, broken and healthy tests
- a bar chart with the failure rate of each flaky or broken test (the top 10), and a line where FIX FIRST starts
- a line chart for the three flakiest tests. It shows how the chance of seeing a failure grows with each rerun, and where it reaches 95%. It is the same 1 - (1 - p)^k idea from above, drawn as a picture
- a table with one row for every test, coloured by flaky, broken or healthy
- a Download CSV button that saves the same table

When you move the mouse over a chart, you see the exact numbers. The colours follow the light or dark setting of your computer.

### How it works

`web_finder.py` starts a small web server on your own computer, at `127.0.0.1`, so only your computer can reach it. Your browser reads the XML files and sends them to this program. The program uses the same code as the command-line tool, so both give the same numbers. Then it sends the answer back to the page.

The page does not load anything from the internet, and your reports never leave your computer. Test names are shown as plain text. The CSV is made safe for Excel, so a test name that starts with `=` will not run as a formula.

## About the data

I did not use any company data, and none is stored in this repository. Test reports from a workplace can contain private details about products and systems, so I kept them out for privacy and security reasons.

The practice reports in `sample_reports/` are made up. `make_sample_reports.py` creates 20 runs of an imaginary online shop (with a fixed random seed, so you get the same files every time). It also writes `answer_key.txt`, which lists the true answer for every test. That lets me check the tool against a known truth.

If you run the tool on your own reports, it works on your own computer. Nothing is sent anywhere.

## How well it works

I checked the tool against the answer key with `check_against_answer_key.py`. It was right for 11 of 12 tests.

| Test | Truth | Tool said |
| --- | --- | --- |
| test_pay_by_card (failed 9 of 20) | flaky | flaky, FIX FIRST |
| test_login_after_session_timeout (5 of 20) | flaky | flaky, FIX FIRST |
| test_search_autocomplete (1 of 20) | flaky | flaky, WATCH |
| test_invoice_download (20 of 20) | broken | broken |
| 7 other tests | healthy | healthy |
| test_apply_coupon (0 of 20) | flaky | healthy (missed) |

The miss is the most useful part. `test_apply_coupon` is flaky, but it fails only about 2% of the time and did not fail once in my 20 runs. Nothing in the reports shows it, so no rerun-based method could find it. This is exactly why the tool prints the warning about the number of runs.

I made this data myself, so these results only show that the tool does what I designed it to do. They do not tell us how it would do on a real project, where flakiness can also depend on test order, timing or the machine.

## Limits

- It assumes the runs are independent and use the same code.
- With few runs, the failure rates are rough.
- It cannot find a flaky test that never failed in the runs it was given.
- It finds flaky tests but not their cause.
- It reads JUnit XML only. The web page only takes the `.xml` files from the folder you choose.
- I have only tested it on made-up data.

## What I want to do next

- Link it to my other project in this repository, `flaky_classifier.py`, which predicts flaky tests from test features. The Finder's labels could become training data, and the model could point out "healthy" tests that look risky, like the one the Finder missed.
- Add a small desktop window, so people can pick files without a browser.
- Try it on public CI reports from open-source projects.

## How to run it

You need Python 3.8 or newer. No extra packages.

On the command line:

```
python make_sample_reports.py
python flaky_test_finder.py
python flaky_test_finder.py C:\path\to\your\reports
python check_against_answer_key.py
```

The first command makes the practice reports. The second runs the tool on them. The third runs it on your own folder. The fourth compares the tool with the answer key. You can add `--out FOLDER` to choose where the report files are saved.

For the web page:

```
python web_finder.py
```

Then open http://127.0.0.1:8000 in your browser. The program tries to open it for you. Choose a folder with XML reports and press "Find flaky tests". To stop the program, press Ctrl+C in the window where you started it.

Output of the command line on the practice data:

```
FLAKY TESTS (worst first)
  FIX FIRST  shop.CheckoutTests.test_pay_by_card               fails in 45% of runs (9 of 20)   reruns: about 6
  FIX FIRST  shop.LoginTests.test_login_after_session_timeout  fails in 25% of runs (5 of 20)   reruns: about 11
  WATCH      shop.SearchTests.test_search_autocomplete         fails in 5% of runs (1 of 20)   reruns: about 59

BROKEN TESTS (they always fail, so they are not flaky)
  FIX        shop.CheckoutTests.test_invoice_download          failed 20 of 20 runs

HEALTHY TESTS: 8 (no failure seen in these runs)
```

## Files

- `flaky_test_finder.py`: the full tool for the command line
- `web_finder.py`: the web page with the charts, the table and the Download CSV button
- `web_page.png`: a screenshot of the web page
- `make_sample_reports.py`: makes the practice reports and the answer key
- `check_against_answer_key.py`: compares the tool with the truth
- `read_one_report.py`, `read_all_reports.py`, `find_flaky_tests.py`, `advise_on_tests.py`: the same tool in small steps, kept to show how I built it
- `sample_reports/`: the 20 made-up reports

## Credit

Flaky tests are a well-studied topic, and rerunning failed tests is a known technique that many test tools already offer. I am not claiming a new method. The main repository reproduces and extends the FlakeFlagger work (Alshammari, Morris, Hilton and Bell, ICSE 2021) and uses its public dataset. The Finder is separate from that dataset. What I added here is a small, readable tool that gives a clear answer to "how many runs are enough?" and is open about what it cannot see.

Reference: A. Alshammari, C. Morris, M. Hilton and J. Bell, "FlakeFlagger: Predicting Flakiness Without Rerunning Tests", International Conference on Software Engineering (ICSE), 2021. Dataset: <https://zenodo.org/record/4450723>
