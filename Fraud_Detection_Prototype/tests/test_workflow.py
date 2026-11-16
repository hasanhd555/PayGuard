"""Leakage boundaries, policy decisions, artifact consistency and offline execution."""

import warnings
from io import BytesIO

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import ConvergenceWarning

from Fraud_Detection_Prototype import data, evaluate, predict, train
from Fraud_Detection_Prototype.common import FEATURES
from Fraud_Detection_Prototype.metrics import choose_threshold, select_model, threshold_table


def transactions(n=300):
    rng = np.random.default_rng(42)
    frame = pd.DataFrame(rng.normal(size=(n, len(FEATURES))), columns=FEATURES)
    frame["Amount"] = rng.uniform(0, 100, n)
    frame["Time"] = np.arange(n)
    frame["Class"] = (np.arange(n) % 7 == 0).astype(int)
    frame["V1"] += frame.Class * 3
    return frame[data.COLUMNS]


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("fraud")
    path = root / "sample.csv"
    transactions().to_csv(path, index=False)
    run_dir = root / "training"
    manifest = train.run(path, run_dir)
    return root, path, run_dir, manifest


def test_split_order_and_tied_timestamps():
    frame = transactions()
    frame["Time"] = frame.Time // 11
    shuffled = frame.sample(frac=1, random_state=1)
    splits, boundaries = data.chronological_split(shuffled)
    assert splits["train"].Time.max() < splits["validation"].Time.min()
    assert splits["validation"].Time.max() < splits["test"].Time.min()
    assert sum(map(len, splits.values())) == len(frame)
    repeated, _ = data.chronological_split(shuffled, boundaries)
    for name in splits:
        pd.testing.assert_frame_equal(splits[name], repeated[name])


def test_exact_duplicates_and_later_events(tmp_path):
    frame = transactions()
    later = frame.iloc[[0]].copy()
    later["Time"] = 1000
    path = tmp_path / "sample.csv"
    pd.concat([frame, frame.iloc[[0]], later]).to_csv(path, index=False)
    cleaned, audit = data.load_data(path)
    assert audit["exact_duplicates_removed"] == 1
    assert len(cleaned) == len(frame) + 1
    splits, _ = data.chronological_split(cleaned)
    assert data.split_audit(splits)["test"]["feature_rows_seen_in_earlier_split"] == 1


@pytest.mark.parametrize("change", ["missing", "extra", "label", "nan", "inf", "text", "amount", "time"])
def test_invalid_inputs(tmp_path, change):
    frame = transactions()
    if change == "missing":
        frame = frame.drop(columns="V1")
    elif change == "extra":
        frame["unexpected"] = 1
    elif change == "text":
        frame["V1"] = "bad"
    else:
        column, value = {"label": ("Class", 2), "nan": ("V1", np.nan),
                         "inf": ("V1", np.inf), "amount": ("Amount", -1),
                         "time": ("Time", -1)}[change]
        frame.loc[0, column] = value
    path = tmp_path / "bad.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        data.load_data(path)


def test_split_missing_fraud_fails():
    frame = transactions()
    frame.loc[frame.Time >= 240, "Class"] = 0
    with pytest.raises(ValueError, match="test partition needs both classes"):
        data.chronological_split(frame)


def test_download_records_provenance_without_network(tmp_path, monkeypatch):
    payload = transactions().to_csv(index=False).encode()
    monkeypatch.setattr(data.urllib.request, "urlopen", lambda *a, **k: BytesIO(payload))
    path = tmp_path / "download.csv"
    audit = data.download(path)
    assert path.read_bytes() == payload
    assert audit["sha256"] == data.sha256(path)
    assert path.with_suffix(".source.json").exists()
    with pytest.raises(FileExistsError):
        data.download(path)


def test_failed_download_cleans_only_its_own_partial_file(tmp_path, monkeypatch):
    path = tmp_path / "download.csv"
    temporary = path.with_suffix(".download")
    temporary.write_text("another process's partial file")
    with pytest.raises(FileExistsError):
        data.download(path)
    assert temporary.read_text() == "another process's partial file"
    temporary.unlink()
    monkeypatch.setattr(data.urllib.request, "urlopen", lambda *a, **k: BytesIO(b"bad,data\n1,2\n"))
    with pytest.raises(ValueError):
        data.download(path)
    assert not temporary.exists()
    assert not path.exists()


def test_scaler_uses_training_only(completed_run):
    _, path, run_dir, _ = completed_run
    frame, _ = data.load_data(path)
    splits, _ = data.chronological_split(frame)
    pipeline = joblib.load(run_dir / "logistic_regression.joblib")
    np.testing.assert_allclose(pipeline["scale"].mean_, splits["train"][FEATURES].mean())
    before = pipeline["scale"].mean_.copy()
    pipeline.predict_proba(splits["test"][FEATURES] + 100)
    np.testing.assert_array_equal(pipeline["scale"].mean_, before)


def test_cost_scan_matches_brute_force_and_keeps_ties_together():
    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, 100)
    scores = np.round(rng.uniform(size=100), 1)
    rows = threshold_table(y, scores, 5, 100)
    assert len(rows) == len(set(scores)) + 1
    for row in rows:
        flags = scores >= row["threshold"]
        assert row["fp"] == ((y == 0) & flags).sum()
        assert row["fn"] == ((y == 1) & ~flags).sum()
        assert row["cost"] == row["fp"] * 5 + row["fn"] * 100
    best = choose_threshold(y, scores)
    assert (best["cost"], best["alerts"]) == min((row["cost"], row["alerts"]) for row in rows)


def test_no_alert_policy_and_ties():
    row = choose_threshold([0, 1], [1., 1.], 1, 1)
    assert row["alerts"] == 0
    assert row["threshold"] > 1
    assert select_model({"random_forest": {"modeled_cost": 100},
                         "logistic_regression": {"modeled_cost": 100}}) == "logistic_regression"


@pytest.mark.parametrize("fp,fn", [(0, 1), (1, -1), (np.nan, 1), (1, np.inf)])
def test_invalid_costs(fp, fn):
    with pytest.raises(ValueError):
        choose_threshold([0, 1], [.1, .9], fp, fn)


def test_train_selection_unaffected_by_test_labels(completed_run):
    root, path, _, manifest = completed_run
    frame = pd.read_csv(path)
    mask = frame.Time >= manifest["boundaries"]["test_start"]
    frame.loc[mask, "Class"] = 1 - frame.loc[mask, "Class"]
    changed = root / "changed.csv"
    frame.to_csv(changed, index=False)
    second = train.run(changed, root / "changed_run")
    # CSV round-tripping can change the last floating-point bit of a score.
    for name, result in manifest["validation"].items():
        assert second["validation"][name] == pytest.approx(result, rel=1e-12, abs=1e-12)
    assert second["selected_model"] == manifest["selected_model"]


def test_convergence_warning_stops_training(tmp_path, monkeypatch):
    class NonConverging:
        def fit(self, *_):
            warnings.warn("did not converge", ConvergenceWarning)
    path = tmp_path / "sample.csv"
    transactions().to_csv(path, index=False)
    monkeypatch.setattr(train, "build_models", lambda: {"logistic_regression": NonConverging()})
    with pytest.raises(ConvergenceWarning):
        train.run(path, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()


def test_evaluation_preserves_selection_and_artifacts(completed_run):
    root, path, run_dir, manifest = completed_run
    fingerprint = data.sha256(run_dir / "manifest.json")
    report = evaluate.run(run_dir, path, root / "test")
    assert report["selected_model"] == manifest["selected_model"]
    assert data.sha256(run_dir / "manifest.json") == fingerprint
    for name, result in report["test"].items():
        assert result["threshold"] == manifest["validation"][name]["threshold"]
        assert sum(result[key] for key in ("tp", "fp", "fn", "tn")) == manifest["splits"]["test"]["rows"]
    for filename in ("report.json", "comparison.csv", "RESULTS.md", "test_pr.png"):
        assert (root / "test" / filename).exists()
    with pytest.raises(FileExistsError):
        evaluate.run(run_dir, path, root / "test")


def test_fingerprint_mismatch_rejected(completed_run):
    root, _, run_dir, _ = completed_run
    changed = root / "mismatch.csv"
    transactions(301).to_csv(changed, index=False)
    with pytest.raises(ValueError, match="fingerprint"):
        evaluate.run(run_dir, changed, root / "mismatched_output")
    assert not (root / "mismatched_output").exists()


def test_saved_model_prediction_and_column_order(completed_run):
    root, path, run_dir, manifest = completed_run
    frame = pd.read_csv(path).iloc[-10:][FEATURES]
    input_path = root / "new.csv"
    frame.to_csv(input_path, index=False)
    predictions = predict.run(run_dir, input_path, root / "predictions.csv")
    selected = manifest["selected_model"]
    pipeline = joblib.load(run_dir / manifest["models"][selected]["artifact"])
    cutoff = manifest["validation"][selected]["threshold"]
    np.testing.assert_array_equal(predictions.requires_review, predictions.fraud_score >= cutoff)
    reordered = predict.score(frame[frame.columns[::-1]], pipeline, FEATURES, cutoff)
    pd.testing.assert_frame_equal(predictions, reordered)
    assert predictions.fraud_score.between(0, 1).all()
    with pytest.raises(ValueError, match="Missing columns"):
        predict.score(frame.drop(columns="V1"), pipeline, FEATURES, cutoff)
    with pytest.raises(FileExistsError):
        predict.run(run_dir, input_path, root / "predictions.csv")
    with pytest.raises(FileExistsError):
        train.run(path, run_dir)
