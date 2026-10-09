"""
Flaky test prediction + rerun-budget analysis (reproduction & extension of FlakeFlagger).

Inputs (both come from https://github.com/AlshammariA/FlakeFlagger):
  --features  flakiness-predicter/result/processed_data.csv   (test features + 'flaky' label)
  --reruns    test-rerun-scripts/test_results.csv             (10,000-rerun outcomes)

Usage:
  python flaky_classifier.py --features processed_data.csv --reruns test_results.csv --out results

Outputs in --out/: metrics.csv, budget.csv, detection_curve.png, budget_comparison.png, summary.txt
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, f1_score, matthews_corrcoef,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

RANDOM_STATE = 42
FEATURES = [
    "assertion-roulette", "conditional-test-logic", "eager-test", "fire-and-forget",
    "indirect-testing", "mystery-guest", "resource-optimism", "test-run-war",
    "testLength", "numAsserts", "numCoveredLines", "ExecutionTime",
    "projectSourceLinesCovered", "projectSourceClassesCovered",
    "hIndexModificationsPerCoveredLine_window5", "hIndexModificationsPerCoveredLine_window10",
    "hIndexModificationsPerCoveredLine_window25", "hIndexModificationsPerCoveredLine_window50",
    "hIndexModificationsPerCoveredLine_window75", "hIndexModificationsPerCoveredLine_window100",
    "hIndexModificationsPerCoveredLine_window500", "hIndexModificationsPerCoveredLine_window10000",
    "num_third_party_libs",
]


def load(features_path, reruns_path):
    feats = pd.read_csv(features_path)
    runs = pd.read_csv(reruns_path)
    # Join key: feature file uses lower-case "package.Class.method"; rerun file uses "package.Class#method".
    runs["key"] = runs["Test"].str.replace("#", ".", regex=False).str.lower()
    runs = runs.drop_duplicates("key")
    df = feats.merge(runs[["key", "IsFlaky", "NumFailingRuns", "NumPassingRuns",
                           "FirstFailingRunID", "FirstPassingRunID"]],
                     left_on="test_name", right_on="key", how="left")
    return feats, runs, df


def detection_run(df):
    """Reruns needed to see BOTH a pass and a fail (assumes run IDs are 0-indexed)."""
    return np.maximum(df["FirstFailingRunID"], df["FirstPassingRunID"]) + 1


def rerun_detection_curve(runs, out):
    flaky = runs[runs["IsFlaky"] == 1].copy()
    flaky["det"] = detection_run(flaky)
    ks = [2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
    pct = [(flaky["det"] <= k).mean() * 100 for k in ks]
    plt.figure(figsize=(6.5, 4))
    plt.plot(ks, pct, marker="o")
    plt.xscale("log")
    plt.xlabel("Number of reruns per test")
    plt.ylabel("% of flaky tests detected")
    plt.title("How many reruns does it take to catch a flaky test?")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out, "detection_curve.png"), dpi=150)
    plt.close()
    return dict(zip(ks, pct))


def models():
    return {
        "Majority class": DummyClassifier(strategy="most_frequent"),
        "Logistic regression": make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced")),
        "Random forest": make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample",
                                   min_samples_leaf=3, n_jobs=-1, random_state=RANDOM_STATE)),
        "Gradient boosting": HistGradientBoostingClassifier(
            class_weight="balanced", max_iter=300, learning_rate=0.05,
            random_state=RANDOM_STATE),
    }


def cross_validate(df, n_splits=5):
    """Group k-fold by project, so tests from one project never appear in train and test."""
    X, y, groups = df[FEATURES], df["flaky"].astype(int).values, df["project"].values
    gkf = GroupKFold(n_splits=n_splits)
    rows, oof = [], {}
    for name, model in models().items():
        scores = np.zeros(len(df))
        for tr, te in gkf.split(X, y, groups):
            model.fit(X.iloc[tr], y[tr])
            scores[te] = (model.predict_proba(X.iloc[te])[:, 1]
                          if hasattr(model, "predict_proba") else model.predict(X.iloc[te]))
        # Pick the decision threshold by maximising F1 on the pooled out-of-fold scores
        # (reported separately from the default 0.5 so it is transparent).
        pred05 = (scores >= 0.5).astype(int)
        grid = np.unique(np.quantile(scores, np.linspace(0.5, 0.999, 200)))
        best_t = max(grid, key=lambda t: f1_score(y, (scores >= t).astype(int), zero_division=0))
        predbest = (scores >= best_t).astype(int)
        rows.append({
            "model": name,
            "PR-AUC": average_precision_score(y, scores),
            "ROC-AUC": roc_auc_score(y, scores) if len(set(scores)) > 1 else 0.5,
            "precision@0.5": precision_score(y, pred05, zero_division=0),
            "recall@0.5": recall_score(y, pred05, zero_division=0),
            "F1@0.5": f1_score(y, pred05, zero_division=0),
            "MCC@0.5": matthews_corrcoef(y, pred05),
            "tuned_threshold": best_t,
            "precision@tuned": precision_score(y, predbest, zero_division=0),
            "recall@tuned": recall_score(y, predbest, zero_division=0),
            "F1@tuned": f1_score(y, predbest, zero_division=0),
        })
        oof[name] = scores
    return pd.DataFrame(rows), oof


def budget_analysis(df, scores, budget_per_test=(5, 10, 20, 50, 100, 200), big_k=(200, 1000, 10000)):
    """Same total rerun budget, two strategies:
       A) uniform  : rerun every test k times.
       B) guided   : rerun only the top-M tests by model score, k_big times each (M = budget / k_big).
       Metric: % of truly flaky tests whose flakiness is actually observed."""
    d = df[df["IsFlaky"].notna()].copy()
    d["score"] = scores[d.index]
    d["det"] = detection_run(d)
    flaky_total = int((d["IsFlaky"] == 1).sum())
    n = len(d)
    ranked = d.sort_values("score", ascending=False)
    rows = []
    for k in budget_per_test:
        budget = k * n
        uniform = int(((d["IsFlaky"] == 1) & (d["det"] <= k)).sum())
        row = {"budget_reruns_per_test": k, "total_reruns": budget,
               "uniform_found_%": 100 * uniform / flaky_total}
        for kb in big_k:
            m = min(n, budget // kb)
            top = ranked.head(m)
            found = int(((top["IsFlaky"] == 1) & (top["det"] <= kb)).sum())
            row[f"guided_{kb}reruns_tests_selected"] = m
            row[f"guided_{kb}reruns_found_%"] = 100 * found / flaky_total
        rows.append(row)
    return pd.DataFrame(rows), flaky_total, n


def plot_budget(bdf, out):
    cols = [c for c in bdf.columns if c.endswith("found_%")]
    plt.figure(figsize=(7, 4))
    for c in cols:
        plt.plot(bdf["budget_reruns_per_test"], bdf[c], marker="o",
                 label=c.replace("_found_%", "").replace("_", " "))
    plt.xscale("log")
    plt.xlabel("Average reruns per test (total budget / number of tests)")
    plt.ylabel("% of flaky tests found")
    plt.title("Same rerun budget: uniform vs model-guided")
    plt.legend(fontsize=8)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out, "budget_comparison.png"), dpi=150)
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--reruns", required=True)
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    feats, runs, df = load(a.features, a.reruns)
    lines = []
    def say(s=""):
        print(s)
        lines.append(s)

    say(f"Rerun file: {len(runs)} tests, {int(runs['IsFlaky'].sum())} flaky "
        f"({runs['IsFlaky'].mean()*100:.2f}%)")
    say(f"Feature file: {len(feats)} tests, {int(feats['flaky'].sum())} flaky, "
        f"{feats['project'].nunique()} projects")
    say(f"Matched to rerun data: {int(df['IsFlaky'].notna().sum())} / {len(df)}")

    curve = rerun_detection_curve(runs, a.out)
    say("\nRerun detection curve (% of flaky tests whose flakiness is observed within k reruns):")
    for k, p in curve.items():
        say(f"  k={k:>6}: {p:5.1f}%")

    metrics, oof = cross_validate(df)
    metrics.round(3).to_csv(os.path.join(a.out, "metrics.csv"), index=False)
    say("\nProject-grouped 5-fold cross-validation (pooled out-of-fold predictions):")
    say(metrics.round(3).to_string(index=False))

    best = metrics.sort_values("PR-AUC", ascending=False).iloc[0]["model"]
    bdf, flaky_total, n = budget_analysis(df, oof[best])
    bdf.round(1).to_csv(os.path.join(a.out, "budget.csv"), index=False)
    plot_budget(bdf, a.out)
    say(f"\nRerun-budget analysis using out-of-fold scores from: {best}")
    say(f"({flaky_total} flaky tests among {n} matched tests)")
    say(bdf.round(1).to_string(index=False))

    with open(os.path.join(a.out, "summary.txt"), "w") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    main()
