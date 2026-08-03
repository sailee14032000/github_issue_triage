import json
from pathlib import Path
from typing import Any

from models.category_enum import IssueCategory


GOLDEN_PATH = Path("data/corpus_golden_data.json")
LABELS = [
    IssueCategory.BUG.value,
    IssueCategory.ENHANCEMENT.value,
    IssueCategory.QUESTION.value,
    IssueCategory.DOCUMENTATION.value,
    IssueCategory.SECURITY.value,
    IssueCategory.OTHER.value,
]
_LABEL_SET = set(LABELS)


def _normalize_title(title: str) -> str:
    return " ".join((title or "").strip().lower().split())


def _safe_label(value: str | None) -> str:
    if value in _LABEL_SET:
        return value
    return IssueCategory.OTHER.value


def _load_golden_entries() -> list[dict[str, Any]]:
    if not GOLDEN_PATH.exists():
        raise FileNotFoundError(f"Golden dataset not found: {GOLDEN_PATH}")

    with GOLDEN_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict) and isinstance(payload.get("issues"), list):
        entries = payload["issues"]
    else:
        raise ValueError("Unsupported golden dataset JSON shape")

    return entries


def _build_confusion(y_true: list[str], y_pred: list[str]) -> dict[str, dict[str, int]]:
    matrix = {actual: {pred: 0 for pred in LABELS} for actual in LABELS}
    for actual, pred in zip(y_true, y_pred):
        matrix[actual][pred] += 1
    return matrix


def _compute_model_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    total = len(y_true)
    correct = sum(1 for actual, pred in zip(y_true, y_pred) if actual == pred)
    accuracy = (correct / total) if total else 0.0

    per_class = {}
    for label in LABELS:
        tp = sum(1 for actual, pred in zip(y_true, y_pred) if actual == label and pred == label)
        fp = sum(1 for actual, pred in zip(y_true, y_pred) if actual != label and pred == label)
        fn = sum(1 for actual, pred in zip(y_true, y_pred) if actual == label and pred != label)

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(1 for actual in y_true if actual == label),
        }

    return {
        "overall_accuracy": accuracy,
        "correct_count": correct,
        "per_class": per_class,
        "confusion_matrix": _build_confusion(y_true, y_pred),
    }


def evaluate_scored_results(prediction_rows: list[dict[str, Any]]) -> dict[str, Any]:
    golden_entries = _load_golden_entries()
    golden_by_key: dict[tuple[Any, str], dict[str, Any]] = {}
    golden_titles_by_id: dict[Any, set[str]] = {}
    for entry in golden_entries:
        issue_id = entry.get("issue_id")
        normalized_title = _normalize_title(entry.get("title", ""))
        golden_by_key[(issue_id, normalized_title)] = entry
        golden_titles_by_id.setdefault(issue_id, set()).add(entry.get("title", ""))

    y_true: list[str] = []
    y_pred_a: list[str] = []
    y_pred_b: list[str] = []
    title_mismatches: list[dict[str, Any]] = []
    unmatched_issue_ids: list[Any] = []
    disagreements: list[dict[str, Any]] = []

    for row in prediction_rows:
        issue_id = row.get("issue_id")
        predicted_title = row.get("title", "")
        row_key = (issue_id, _normalize_title(predicted_title))
        golden = golden_by_key.get(row_key)

        if not golden:
            if issue_id in golden_titles_by_id:
                golden_title = sorted(golden_titles_by_id[issue_id])[0]
                title_mismatches.append(
                    {
                        "issue_id": issue_id,
                        "predicted_title": predicted_title,
                        "golden_title": golden_title,
                    }
                )
            else:
                unmatched_issue_ids.append(issue_id)
            continue

        if not golden.get("is_scored") or golden.get("ground_truth_label") not in _LABEL_SET:
            continue

        if _normalize_title(predicted_title) != _normalize_title(golden.get("title", "")):
            title_mismatches.append(
                {
                    "issue_id": issue_id,
                    "predicted_title": predicted_title,
                    "golden_title": golden.get("title", ""),
                }
            )
            continue

        ground_truth_label = golden["ground_truth_label"]
        pred_a = _safe_label((row.get("model_a") or {}).get("category"))
        pred_b = _safe_label((row.get("model_b") or {}).get("category"))

        y_true.append(ground_truth_label)
        y_pred_a.append(pred_a)
        y_pred_b.append(pred_b)

        if pred_a != pred_b:
            disagreements.append(
                {
                    "issue_id": issue_id,
                    "title": row.get("title", ""),
                    "ground_truth_label": ground_truth_label,
                    "model_a_prediction": pred_a,
                    "model_b_prediction": pred_b,
                    "body": row.get("body", ""),
                    "model_a_raw_output": (row.get("model_a") or {}).get("raw_output"),
                    "model_b_raw_output": (row.get("model_b") or {}).get("raw_output"),
                }
            )

    scored_count = len(y_true)

    return {
        "match_summary": {
            "golden_total": len(golden_entries),
            "id_matched": len(golden_entries) - len(unmatched_issue_ids),
            "scored_count": scored_count,
            "title_mismatch_count": len(title_mismatches),
            "unmatched_issue_count": len(unmatched_issue_ids),
        },
        "model_a": _compute_model_metrics(y_true, y_pred_a),
        "model_b": _compute_model_metrics(y_true, y_pred_b),
        "disagreements": disagreements,
        "title_mismatches": title_mismatches,
    }
