import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

from prompts.triage_prompt import build_triage_prompt
from services.evaluation.scoring_service import evaluate_scored_results
from services.evaluation.unscored_service import evaluate_unscored_results
from services.inference_service import run_model_inference


load_dotenv()

CORPUS_PATH = Path(os.environ.get("CORPUS_PATH", "data/corpus.json"))

try:
    MAX_IN_FLIGHT_CALLS = int(os.environ.get("MAX_IN_FLIGHT_CALLS", "10"))
except ValueError as exc:
    raise ValueError("MAX_IN_FLIGHT_CALLS must be an integer") from exc

if MAX_IN_FLIGHT_CALLS < 1:
    raise ValueError("MAX_IN_FLIGHT_CALLS must be at least 1")


def _load_corpus_issues() -> list[dict]:
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(f"Corpus file not found: {CORPUS_PATH}")

    with CORPUS_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict) and isinstance(payload.get("issues"), list):
        return payload["issues"]
    if isinstance(payload, list):
        return payload
    raise ValueError("Unsupported corpus JSON shape")


def run_model_comparison(model_a: str, model_b: str) -> dict:
    issues = _load_corpus_issues()
    rows = []

    for issue in issues:
        issue_id = issue.get("issue_id")
        title = issue.get("title", "") or ""
        body = issue.get("body", "") or ""
        prompt = build_triage_prompt(title, body)

        rows.append(
            {
                "issue_id": issue_id,
                "title": title,
                "body": body,
                "is_scored": issue.get("is_scored"),
                "model_a": {
                    "category": None,
                    "raw_output": None,
                    "error": None,
                },
                "model_b": {
                    "category": None,
                    "raw_output": None,
                    "error": None,
                },
                "_prompt": prompt,
            }
        )

    with ThreadPoolExecutor(max_workers=MAX_IN_FLIGHT_CALLS) as executor:
        futures = {}
        for row_index, row in enumerate(rows):
            prompt = row["_prompt"]
            futures[executor.submit(run_model_inference, model_a, prompt)] = (row_index, "model_a")
            futures[executor.submit(run_model_inference, model_b, prompt)] = (row_index, "model_b")

        for future in as_completed(futures):
            row_index, model_key = futures[future]
            try:
                output = future.result()
                rows[row_index][model_key]["category"] = output.get("category")
                rows[row_index][model_key]["raw_output"] = output.get("response")
            except Exception as exc:  # Keep processing remaining entries.
                rows[row_index][model_key]["error"] = str(exc)

    for row in rows:
        del row["_prompt"]

    model_a_success = sum(1 for row in rows if row["model_a"]["error"] is None)
    model_b_success = sum(1 for row in rows if row["model_b"]["error"] is None)
    scored_metrics = evaluate_scored_results(rows)
    unscored_metrics = evaluate_unscored_results(rows)

    return {
        "ok": True,
        "message": "Comparison completed for all corpus entries.",
        "request": {
            "model_a": model_a,
            "model_b": model_b,
            "corpus_path": str(CORPUS_PATH),
        },
        "summary": {
            "total_issues": len(rows),
            "model_a_success": model_a_success,
            "model_a_errors": len(rows) - model_a_success,
            "model_b_success": model_b_success,
            "model_b_errors": len(rows) - model_b_success,
        },
        "results": rows,
        "scored": scored_metrics,
        "unscored": unscored_metrics,
        "operational": {},
    }
