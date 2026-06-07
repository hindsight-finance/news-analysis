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
import polars as pl
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning, UndefinedMetricWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

# Scoped suppression (QUAL-01): silence only the expected sklearn modelling warnings
# (LogisticRegression not converging, undefined metrics on tiny CV folds) instead of a
# blanket filterwarnings("ignore") that would hide every unrelated warning repo-wide.
warnings.filterwarnings("ignore", category=ConvergenceWarning)
warnings.filterwarnings("ignore", category=UndefinedMetricWarning)

DEFAULT_INPUT = Path("data/sweep_analysis_results.parquet")
DEFAULT_OUTPUT_DIR = Path("charts/causal")


def qcut_with_fallback_labels(series: pl.Series, q: int, labels: list[str]) -> pl.Series:
    """Quantile-cut a series; polars resolves duplicate edges via allow_duplicates.

    Unlike pandas (which raises "Bin labels must be one fewer" when duplicate edges
    collapse bins), polars' ``Series.qcut(..., allow_duplicates=True)`` never raises:
    it returns a Categorical assigning only the labels that map to real bins. These
    bins are display/reporting only, so exact edges need not match pandas.
    """
    return series.qcut(q, labels=labels, allow_duplicates=True)


def load_resolved_results(input_path: Path) -> pl.DataFrame:
    df = pl.read_parquet(input_path)
    df = df.filter(pl.col("first_target_hit").is_not_null())
    df = df.with_columns((pl.col("first_target_hit") == "box").cast(pl.Int64).alias("target"))
    return df


def build_features(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.Series]:
    """Engineer notebook model features and binary target.

    Returns a polars feature frame whose ``.columns`` is a stable label list (the
    12 features in their original order) plus the binary target Series. The two
    LabelEncoder columns cross the polars->numpy boundary explicitly via
    ``.to_numpy()`` and are wrapped back into the polars frame; the session-context
    columns are nulls, so ``fill_null(0)`` (NOT fillna) covers them.
    """
    le_event = LabelEncoder()
    event_type_encoded = le_event.fit_transform(df.get_column("event_type").to_numpy())

    le_time = LabelEncoder()
    release_time_encoded = le_time.fit_transform(df.get_column("release_time").to_numpy())

    features = pl.DataFrame(
        {
            "event_type_encoded": event_type_encoded,
            "release_time_encoded": release_time_encoded,
            "first_sweep_high": (df.get_column("first_sweep") == "high").cast(pl.Int64),
            "gap_direction_encoded": df.get_column("gap_6pm_direction").replace_strict(
                {"up": 1, "down": 0, "flat": -1}, default=-1, return_dtype=pl.Int64
            ),
            "range_pct": df.get_column("range_pct"),
            "release_volume": df.get_column("release_volume"),
            "pre_candle_range_pct": df.get_column("pre_candle_range_pct").fill_null(0),
            "pre_candle_volume": df.get_column("pre_candle_volume").fill_null(0),
            "dist_from_midnight_open_pct": df.get_column("dist_from_midnight_open_pct").fill_null(0),
            "dist_from_6pm_open_pct": df.get_column("dist_from_6pm_open_pct").fill_null(0),
            "gap_6pm_pct": df.get_column("gap_6pm_pct").fill_null(0),
            "time_to_first_sweep": df.get_column("time_to_first_sweep"),
        }
    )

    y = df.get_column("target")
    return features, y


def cv_folds(y: pl.Series, desired: int = 5) -> int:
    """Cap CV folds at the smallest class count; polars-only (uses value_counts)."""
    class_counts = y.value_counts()
    if class_counts.height == 0:
        return 0
    min_count = int(class_counts.get_column("count").min())
    return int(max(0, min(desired, min_count)))


def print_cv_score(name: str, model, X: np.ndarray, y_np: np.ndarray, folds: int) -> None:
    """Print cross-validated accuracy. ``folds`` is precomputed on the polars y
    Series (in run(), before the numpy boundary) and passed in, so this helper
    never calls ``cv_folds`` on a numpy array."""
    if folds >= 2:
        scores = cross_val_score(model, X, y_np, cv=folds)
        print(f"{name} CV Accuracy: {scores.mean() * 100:.1f}% (+/- {scores.std() * 100:.1f}%)")
    else:
        print(f"{name} CV Accuracy: skipped; need at least 2 samples in each class")


def plot_feature_importance(importance: pl.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = plt.cm.Blues(np.linspace(0.3, 1, importance.height))
    ax.barh(
        importance.get_column("feature").to_list(),
        importance.get_column("importance").to_numpy(),
        color=colors,
    )
    ax.set_xlabel("Importance", fontsize=12)
    ax.set_title("Feature Importance (Random Forest)", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_logistic_coefficients(coefs: pl.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 8))
    coef_values = coefs.get_column("coefficient").to_list()
    colors = ["#2ecc71" if c < 0 else "#e74c3c" for c in coef_values]
    ax.barh(coefs.get_column("feature").to_list(), coef_values, color=colors)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xlabel("Coefficient (Standardized)", fontsize=12)
    ax.set_title("Logistic Regression: Effect Direction\n← Favors REVERSAL | Favors MOMENTUM →", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_event_edges(event_stats: pl.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 10))
    event_stats_sorted = event_stats.sort("momentum_rate")
    momentum = event_stats_sorted.get_column("momentum_rate").to_numpy()
    colors = ["#2ecc71" if x < 0.5 else "#e74c3c" for x in momentum]
    ax.barh(
        range(event_stats_sorted.height),
        momentum * 100 - 50,
        color=colors,
        alpha=0.85,
        edgecolor="black",
        linewidth=0.5,
    )
    ax.set_yticks(range(event_stats_sorted.height))
    event_names = event_stats_sorted.get_column("event_type").to_list()
    counts = event_stats_sorted.get_column("n").to_list()
    ax.set_yticklabels([f"{e} (n={n})" for e, n in zip(event_names, counts)])
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
    target_sum = int(df.get_column("target").sum())
    target_mean = df.get_column("target").mean()
    print(f"Resolved trades: {df.height}")
    print(f"Momentum: {target_sum} ({target_mean * 100:.1f}%)")
    print(f"Reversal: {df.height - target_sum} ({(1 - target_mean) * 100:.1f}%)")
    print("\nAvailable columns:")
    print(df.columns)

    features, y = build_features(df)
    print(f"\nTotal features: {features.width}")
    for col in features.columns:
        print(f"  • {col}")

    # CV fold count must be derived from the polars y Series (value_counts) BEFORE
    # the numpy boundary; passing a numpy array to cv_folds would raise AttributeError.
    folds = cv_folds(y)

    # --- The single polars -> numpy boundary (MIGRATE-03). Convert exactly once;
    # feature_names is retained for importance / coefficient / tree labels. ---
    feature_names = features.columns
    X = features.to_numpy()
    y_np = y.to_numpy()

    rf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
    rf.fit(X, y_np)
    print_cv_score("Random Forest", rf, X, y_np, folds)
    print(f"Baseline (always predict majority): {max(y_np.mean(), 1 - y_np.mean()) * 100:.1f}%")

    importance = pl.DataFrame({"feature": feature_names, "importance": rf.feature_importances_}).sort("importance")
    plot_feature_importance(importance, output_dir / "feature_importance.png")
    print("\nFeature Importance Ranking:")
    print(importance.sort("importance", descending=True))

    tree = DecisionTreeClassifier(max_depth=4, min_samples_leaf=25, random_state=42)
    tree.fit(X, y_np)
    print_cv_score("Decision Tree", tree, X, y_np, folds)

    fig, ax = plt.subplots(figsize=(28, 14))
    plot_tree(tree, feature_names=feature_names, class_names=["Reversal", "Momentum"], filled=True, rounded=True, fontsize=9, ax=ax)
    ax.set_title("Decision Tree: Predicting Momentum vs Reversal", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_dir / "decision_tree.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    lr = LogisticRegression(random_state=42, max_iter=1000)
    lr.fit(X_scaled, y_np)
    coefs = pl.DataFrame({"feature": feature_names, "coefficient": lr.coef_[0]}).sort("coefficient")
    plot_logistic_coefficients(coefs, output_dir / "logistic_coefficients.png")
    print("\nLogistic Regression Coefficients:")
    print("Positive = pushes toward MOMENTUM")
    print("Negative = pushes toward REVERSAL\n")
    print(coefs)

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
    correlations = pl.DataFrame(
        {
            "feature": numeric_features,
            "correlation": [
                float(np.corrcoef(features.get_column(f).to_numpy(), y_np)[0, 1]) for f in numeric_features
            ],
        }
    ).sort("correlation")
    print("\nCorrelation with MOMENTUM outcome:")
    print(correlations)

    event_stats = (
        df.group_by("event_type")
        .agg(
            pl.len().alias("n"),
            pl.col("target").mean().alias("momentum_rate"),
            pl.col("range_pct").mean().alias("avg_range"),
            pl.col("release_volume").mean().alias("avg_volume"),
            pl.col("dist_from_midnight_open_pct").mean().alias("avg_dist_midnight"),
        )
        .with_columns(
            (1 - pl.col("momentum_rate")).alias("reversal_rate"),
            ((pl.col("momentum_rate") - 0.5).abs() * 100).alias("edge"),
            pl.when(pl.col("momentum_rate") > 0.5).then(pl.lit("MOMENTUM")).otherwise(pl.lit("REVERSAL")).alias("direction"),
        )
        .sort("edge", descending=True)
    )
    event_stats.write_csv(output_dir / "event_stats.csv")
    print("\nEvents ranked by edge:")
    print(event_stats.select("event_type", "n", "momentum_rate", "edge", "direction"))
    plot_event_edges(event_stats, output_dir / "event_edge.png")

    gap_stats = df.group_by("gap_6pm_direction").agg(pl.len().alias("n"), pl.col("target").mean().alias("momentum_rate"))
    print("\nGap Direction (6pm):")
    print(gap_stats)

    df = df.with_columns(
        qcut_with_fallback_labels(
            df.get_column("dist_from_midnight_open_pct").fill_null(0), 4, ["Q1 (far below)", "Q2", "Q3", "Q4 (far above)"]
        ).alias("midnight_dist_quartile")
    )
    midnight_stats = df.group_by("midnight_dist_quartile").agg(pl.len().alias("n"), pl.col("target").mean().alias("momentum_rate"))
    print("\nDistance from Midnight Open:")
    print(midnight_stats)

    event_dummies = df.select("event_type").to_dummies(columns=["event_type"])
    readable_extra = features.select("first_sweep_high", "range_pct", "release_volume", "dist_from_midnight_open_pct", "gap_6pm_pct")
    x_readable = pl.concat([event_dummies, readable_extra], how="horizontal")
    tree_readable = DecisionTreeClassifier(max_depth=3, min_samples_leaf=40, random_state=42)
    tree_readable.fit(x_readable.to_numpy(), y_np)
    print("\nDecision Rules:")
    print(export_text(tree_readable, feature_names=x_readable.columns, max_depth=3))

    print("\n" + "=" * 70)
    print("KEY FINDINGS")
    print("=" * 70)
    print("\nMOST PREDICTIVE FEATURES (Random Forest):")
    for row in importance.sort("importance", descending=True).head(5).iter_rows(named=True):
        print(f"   • {row['feature']}: {row['importance']:.3f}")
    print("\nMOMENTUM-FAVORING EVENTS (play the box):")
    for row in event_stats.filter(pl.col("direction") == "MOMENTUM").head(5).iter_rows(named=True):
        print(f"   • {row['event_type']}: {row['momentum_rate'] * 100:.0f}% momentum (n={row['n']})")
    print("\nREVERSAL-FAVORING EVENTS (play the opposite):")
    for row in event_stats.filter(pl.col("direction") == "REVERSAL").head(5).iter_rows(named=True):
        print(f"   • {row['event_type']}: {row['reversal_rate'] * 100:.0f}% reversal (n={row['n']})")
    print("\nSESSION CONTEXT INSIGHTS:")
    for row in correlations.iter_rows(named=True):
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
