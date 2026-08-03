import json
from collections import Counter
from pathlib import Path
from typing import Any

from models.category_enum import IssueCategory


LABELS = [
    IssueCategory.BUG.value,
    IssueCategory.ENHANCEMENT.value,
    IssueCategory.QUESTION.value,
    IssueCategory.DOCUMENTATION.value,
    IssueCategory.SECURITY.value,
    IssueCategory.OTHER.value,
]
_LABEL_SET = set(LABELS)
GOLDEN_PATH = Path("data/corpus_golden_data.json")


def _normalize_title(title: str) -> str:
    return " ".join((title or "").strip().lower().split())


def _load_golden_id_title_pairs() -> set[tuple[Any, str]]:
    if not GOLDEN_PATH.exists():
        return set()

    with GOLDEN_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict) and isinstance(payload.get("issues"), list):
        entries = payload["issues"]
    else:
        return set()

    pairs: set[tuple[Any, str]] = set()
    for item in entries:
        pairs.add((item.get("issue_id"), _normalize_title(item.get("title", ""))))
    return pairs


def _safe_label(value: str | None) -> str:
    if value in _LABEL_SET:
        return value
    return IssueCategory.OTHER.value


def evaluate_unscored_results(prediction_rows: list[dict[str, Any]]) -> dict[str, Any]:
    unscored_rows: list[dict[str, Any]] = []
    dist_a = Counter({label: 0 for label in LABELS})
    dist_b = Counter({label: 0 for label in LABELS})
    agreement_count = 0
    golden_pairs = _load_golden_id_title_pairs()

    for row in prediction_rows:
        row_key = (row.get("issue_id"), _normalize_title(row.get("title", "")))
        if row_key in golden_pairs:
            continue

        pred_a = _safe_label((row.get("model_a") or {}).get("category"))
        pred_b = _safe_label((row.get("model_b") or {}).get("category"))
        is_disagreement = pred_a != pred_b

        dist_a[pred_a] += 1
        dist_b[pred_b] += 1
        if not is_disagreement:
            agreement_count += 1

        unscored_rows.append(
            {
                "issue_id": row.get("issue_id"),
                "title": row.get("title", ""),
                "body": row.get("body", ""),
                "model_a_prediction": pred_a,
                "model_b_prediction": pred_b,
                "model_a_raw_output": (row.get("model_a") or {}).get("raw_output"),
                "model_b_raw_output": (row.get("model_b") or {}).get("raw_output"),
                "model_a_error": (row.get("model_a") or {}).get("error"),
                "model_b_error": (row.get("model_b") or {}).get("error"),
                "is_disagreement": is_disagreement,
            }
        )

    total_unscored = len(unscored_rows)
    disagreements = [row for row in unscored_rows if row["is_disagreement"]]

    return {
        "summary": {
            "total_unscored": total_unscored,
            "agreement_count": agreement_count,
            "agreement_rate": (agreement_count / total_unscored) if total_unscored else 0.0,
            "disagreement_count": len(disagreements),
        },
        "model_a_distribution": {label: dist_a[label] for label in LABELS},
        "model_b_distribution": {label: dist_b[label] for label in LABELS},
        "rows": unscored_rows,
        "disagreements": disagreements,
    }
