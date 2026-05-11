"""
Causal Factor Analysis: Momentum vs Reversal

Script version of causal_analysis.ipynb. Reads sweep results, engineers factors,
trains simple predictive models, writes charts, and prints decision summaries.
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

warnings.filterwarnings("ignore")

DEFAULT_INPUT = Path("data/sweep_analysis_results.parquet")
DEFAULT_OUTPUT_DIR = Path("charts/causal")


def qcut_with_fallback_labels(series: pd.Series, q: int, labels: list[str]) -> pd.Series:
    """Quantile-cut a series, dropping labels when duplicate edges reduce bins."""
    try:
        return pd.qcut(series, q, labels=labels, duplicates="drop")
    except ValueError as exc:
        if "Bin labels must be one fewer" not in str(exc):
            raise
        return pd.qcut(series, q, duplicates="drop")


def load_resolved_results(input_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(input_path)
    df = df[df["first_target_hit"].notna()].copy()
    df["target"] = (df["first_target_hit"] == "box").astype(int)
    return df.reset_index(drop=True)


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Engineer notebook model features and binary target."""
    features = pd.DataFrame(index=df.index)

    le_event = LabelEncoder()
    features["event_type_encoded"] = le_event.fit_transform(df["event_type"])

    le_time = LabelEncoder()
    features["release_time_encoded"] = le_time.fit_transform(df["release_time"])

    features["first_sweep_high"] = (df["first_sweep"] == "high").astype(int)

    gap_dir_map = {"up": 1, "down": 0, "flat": -1}
    features["gap_direction_encoded"] = df["gap_6pm_direction"].map(gap_dir_map).fillna(-1).astype(int)

    features["range_pct"] = df["range_pct"]
    features["release_volume"] = df["release_volume"]
    features["pre_candle_range_pct"] = df["pre_candle_range_pct"].fillna(0)
    features["pre_candle_volume"] = df["pre_candle_volume"].fillna(0)
    features["dist_from_midnight_open_pct"] = df["dist_from_midnight_open_pct"].fillna(0)
    features["dist_from_6pm_open_pct"] = df["dist_from_6pm_open_pct"].fillna(0)
    features["gap_6pm_pct"] = df["gap_6pm_pct"].fillna(0)
    features["time_to_first_sweep"] = df["time_to_first_sweep"]

    y = df["target"]
    return features, y


def cv_folds(y: pd.Series, desired: int = 5) -> int:
    class_counts = y.value_counts()
    if class_counts.empty:
        return 0
    return int(max(0, min(desired, class_counts.min())))


def print_cv_score(name: str, model, X: pd.DataFrame, y: pd.Series) -> None:
    folds = cv_folds(y)
    if folds >= 2:
        scores = cross_val_score(model, X, y, cv=folds)
        print(f"{name} CV Accuracy: {scores.mean() * 100:.1f}% (+/- {scores.std() * 100:.1f}%)")
    else:
        print(f"{name} CV Accuracy: skipped; need at least 2 samples in each class")


def plot_feature_importance(importance: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = plt.cm.Blues(np.linspace(0.3, 1, len(importance)))
    ax.barh(importance["feature"], importance["importance"], color=colors)
    ax.set_xlabel("Importance", fontsize=12)
    ax.set_title("Feature Importance (Random Forest)", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_logistic_coefficients(coefs: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = ["#2ecc71" if c < 0 else "#e74c3c" for c in coefs["coefficient"]]
    ax.barh(coefs["feature"], coefs["coefficient"], color=colors)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xlabel("Coefficient (Standardized)", fontsize=12)
    ax.set_title("Logistic Regression: Effect Direction\n← Favors REVERSAL | Favors MOMENTUM →", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_event_edges(event_stats: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 10))
    event_stats_sorted = event_stats.sort_values("momentum_rate")
    colors = ["#2ecc71" if x < 0.5 else "#e74c3c" for x in event_stats_sorted["momentum_rate"]]
    ax.barh(
        range(len(event_stats_sorted)),
        event_stats_sorted["momentum_rate"] * 100 - 50,
        color=colors,
        alpha=0.85,
        edgecolor="black",
        linewidth=0.5,
    )
    ax.set_yticks(range(len(event_stats_sorted)))
    ax.set_yticklabels([f"{e} (n={n})" for e, n in zip(event_stats_sorted["event_type"], event_stats_sorted["n"])])
    ax.axvline(0, color="black", linewidth=1.5)
    ax.axvline(-10, color="gray", linestyle="--", alpha=0.3)
    ax.axvline(10, color="gray", linestyle="--", alpha=0.3)
    ax.set_xlabel("Edge (% from 50/50)", fontsize=12)
    ax.set_title("← REVERSAL favored | MOMENTUM favored →", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def run(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = load_resolved_results(input_path)
    print(f"Resolved trades: {len(df)}")
    print(f"Momentum: {df['target'].sum()} ({df['target'].mean() * 100:.1f}%)")
    print(f"Reversal: {(1 - df['target']).sum()} ({(1 - df['target'].mean()) * 100:.1f}%)")
    print("\nAvailable columns:")
    print(df.columns.tolist())

    features, y = build_features(df)
    X = features.copy()
    print(f"\nTotal features: {len(features.columns)}")
    for col in features.columns:
        print(f"  • {col}")

    rf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
    rf.fit(X, y)
    print_cv_score("Random Forest", rf, X, y)
    print(f"Baseline (always predict majority): {max(y.mean(), 1 - y.mean()) * 100:.1f}%")

    importance = pd.DataFrame({"feature": X.columns, "importance": rf.feature_importances_}).sort_values("importance", ascending=True)
    plot_feature_importance(importance, output_dir / "feature_importance.png")
    print("\nFeature Importance Ranking:")
    print(importance.sort_values("importance", ascending=False).to_string(index=False))

    tree = DecisionTreeClassifier(max_depth=4, min_samples_leaf=25, random_state=42)
    tree.fit(X, y)
    print_cv_score("Decision Tree", tree, X, y)

    fig, ax = plt.subplots(figsize=(28, 14))
    plot_tree(tree, feature_names=list(X.columns), class_names=["Reversal", "Momentum"], filled=True, rounded=True, fontsize=9, ax=ax)
    ax.set_title("Decision Tree: Predicting Momentum vs Reversal", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_dir / "decision_tree.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    lr = LogisticRegression(random_state=42, max_iter=1000)
    lr.fit(X_scaled, y)
    coefs = pd.DataFrame({"feature": X.columns, "coefficient": lr.coef_[0]}).sort_values("coefficient")
    plot_logistic_coefficients(coefs, output_dir / "logistic_coefficients.png")
    print("\nLogistic Regression Coefficients:")
    print("Positive = pushes toward MOMENTUM")
    print("Negative = pushes toward REVERSAL\n")
    print(coefs.to_string(index=False))

    numeric_features = [
        "range_pct",
        "release_volume",
        "pre_candle_range_pct",
        "pre_candle_volume",
        "dist_from_midnight_open_pct",
        "dist_from_6pm_open_pct",
        "gap_6pm_pct",
        "time_to_first_sweep",
        "first_sweep_high",
    ]
    correlations = pd.DataFrame({"feature": numeric_features, "correlation": [features[f].corr(y) for f in numeric_features]}).sort_values("correlation")
    print("\nCorrelation with MOMENTUM outcome:")
    print(correlations.to_string(index=False))

    event_stats = (
        df.groupby("event_type")
        .agg(
            n=("target", "count"),
            momentum_rate=("target", "mean"),
            avg_range=("range_pct", "mean"),
            avg_volume=("release_volume", "mean"),
            avg_dist_midnight=("dist_from_midnight_open_pct", "mean"),
        )
        .reset_index()
    )
    event_stats["reversal_rate"] = 1 - event_stats["momentum_rate"]
    event_stats["edge"] = (event_stats["momentum_rate"] - 0.5).abs() * 100
    event_stats["direction"] = event_stats["momentum_rate"].apply(lambda x: "MOMENTUM" if x > 0.5 else "REVERSAL")
    event_stats = event_stats.sort_values("edge", ascending=False)
    event_stats.to_csv(output_dir / "event_stats.csv", index=False)
    print("\nEvents ranked by edge:")
    print(event_stats[["event_type", "n", "momentum_rate", "edge", "direction"]].to_string(index=False))
    plot_event_edges(event_stats, output_dir / "event_edge.png")

    gap_stats = df.groupby("gap_6pm_direction").agg(n=("target", "count"), momentum_rate=("target", "mean")).reset_index()
    print("\nGap Direction (6pm):")
    print(gap_stats.to_string(index=False))

    df["midnight_dist_quartile"] = qcut_with_fallback_labels(
        df["dist_from_midnight_open_pct"].fillna(0), 4, ["Q1 (far below)", "Q2", "Q3", "Q4 (far above)"]
    )
    midnight_stats = df.groupby("midnight_dist_quartile", observed=False).agg(n=("target", "count"), momentum_rate=("target", "mean")).reset_index()
    print("\nDistance from Midnight Open:")
    print(midnight_stats.to_string(index=False))

    event_dummies = pd.get_dummies(df["event_type"], prefix="event")
    X_readable = pd.concat(
        [event_dummies, features[["first_sweep_high", "range_pct", "release_volume", "dist_from_midnight_open_pct", "gap_6pm_pct"]]],
        axis=1,
    )
    tree_readable = DecisionTreeClassifier(max_depth=3, min_samples_leaf=40, random_state=42)
    tree_readable.fit(X_readable, y)
    print("\nDecision Rules:")
    print(export_text(tree_readable, feature_names=list(X_readable.columns), max_depth=3))

    print("\n" + "=" * 70)
    print("KEY FINDINGS")
    print("=" * 70)
    print("\nMOST PREDICTIVE FEATURES (Random Forest):")
    for _, row in importance.sort_values("importance", ascending=False).head(5).iterrows():
        print(f"   • {row['feature']}: {row['importance']:.3f}")
    print("\nMOMENTUM-FAVORING EVENTS (play the box):")
    for _, row in event_stats[event_stats["direction"] == "MOMENTUM"].head(5).iterrows():
        print(f"   • {row['event_type']}: {row['momentum_rate'] * 100:.0f}% momentum (n={row['n']})")
    print("\nREVERSAL-FAVORING EVENTS (play the opposite):")
    for _, row in event_stats[event_stats["direction"] == "REVERSAL"].head(5).iterrows():
        print(f"   • {row['event_type']}: {row['reversal_rate'] * 100:.0f}% reversal (n={row['n']})")
    print("\nSESSION CONTEXT INSIGHTS:")
    for _, row in correlations.iterrows():
        if abs(row["correlation"]) > 0.05:
            direction = "↑ momentum" if row["correlation"] > 0 else "↓ reversal"
            print(f"   • {row['feature']}: {row['correlation']:.3f} ({direction})")

    print(f"\nWrote charts and CSV outputs to {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.input, args.output_dir)
