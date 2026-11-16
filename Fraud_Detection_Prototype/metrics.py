"""Cost-aware validation policy with tied-score handling and no test tuning."""

import numpy as np
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score


def validate_costs(fp_cost: float, fn_cost: float) -> None:
    if not np.isfinite([fp_cost, fn_cost]).all() or min(fp_cost, fn_cost) <= 0:
        raise ValueError("FP and FN costs must be finite and positive")


def threshold_table(y, scores, fp_cost=5., fn_cost=100.) -> list[dict]:
    """Evaluate all attainable decisions in O(n log n), keeping tied scores together."""
    validate_costs(fp_cost, fn_cost)
    y, scores = np.asarray(y), np.asarray(scores, dtype=float)
    if y.ndim != 1 or y.shape != scores.shape or not len(y) or not np.isin(y, [0, 1]).all():
        raise ValueError("Expected nonempty matching binary labels and scores")
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("Scores must be finite and between zero and one")
    order = np.argsort(-scores, kind="stable")
    ordered, labels = scores[order], y[order].astype(int)
    ends = np.r_[np.flatnonzero(np.diff(ordered)), len(y) - 1]
    tp = np.cumsum(labels)[ends]
    fp, fn = ends + 1 - tp, labels.sum() - tp
    cutoffs = np.r_[np.nextafter(ordered[0], np.inf), ordered[ends]]
    tp, fp, fn = np.r_[0, tp], np.r_[0, fp], np.r_[labels.sum(), fn]
    return [{"threshold": float(t), "tp": int(a), "fp": int(b), "fn": int(c),
             "alerts": int(a + b), "cost": float(b * fp_cost + c * fn_cost)}
            for t, a, b, c in zip(cutoffs, tp, fp, fn)]


def choose_threshold(y, scores, fp_cost=5., fn_cost=100.) -> dict:
    return min(threshold_table(y, scores, fp_cost, fn_cost),
               key=lambda row: (row["cost"], row["alerts"]))


def evaluate(y, scores, threshold, fp_cost=5., fn_cost=100.) -> dict:
    validate_costs(fp_cost, fn_cost)
    y, scores = np.asarray(y), np.asarray(scores)
    tn, fp, fn, tp = confusion_matrix(y, scores >= threshold, labels=[0, 1]).ravel()
    return {"average_precision": float(average_precision_score(y, scores)),
            "roc_auc": float(roc_auc_score(y, scores)), "threshold": float(threshold),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
            "precision": float(tp / (tp + fp)) if tp + fp else 0.,
            "recall": float(tp / (tp + fn)), "false_positive_rate": float(fp / (fp + tn)),
            "alerts": int(tp + fp), "alert_rate": float((tp + fp) / len(y)),
            "modeled_cost": float(fp * fp_cost + fn * fn_cost),
            "cost_per_1000": float((fp * fp_cost + fn * fn_cost) * 1000 / len(y))}


def select_model(validation: dict) -> str:
    """No access to test metrics; prefer the simpler model when costs tie."""
    return min(validation, key=lambda name: (validation[name]["modeled_cost"],
                                            name != "logistic_regression", name))
