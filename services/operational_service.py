from math import ceil
from statistics import median
from typing import Any


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _model_metrics(
    rows: list[dict[str, Any]],
    model_key: str,
    model_name: str,
    correct_count: int,
    wall_clock_seconds: float,
) -> dict[str, Any]:
    calls = [row[model_key] for row in rows]
    costs = [call["cost_usd"] for call in calls if call.get("cost_usd") is not None]
    latencies = [call["latency_seconds"] for call in calls if call.get("latency_seconds") is not None]
    total_cost = round(sum(costs), 8) if len(costs) == len(calls) else None
    total_requests = len(calls)
    error_counts = {
        error_type: sum(1 for call in calls if call.get("error_type") == error_type)
        for error_type in ("rate_limit", "timeout", "other")
    }

    return {
        "model": model_name,
        "total_requests": total_requests,
        "p50_latency_seconds": median(latencies) if latencies else None,
        "p95_latency_seconds": _percentile(latencies, 0.95),
        "throughput_requests_per_second": (
            total_requests / wall_clock_seconds if wall_clock_seconds else 0.0
        ),
        "error_rates": {
            error_type: count / total_requests if total_requests else 0.0
            for error_type, count in error_counts.items()
        },
        "total_cost_usd": total_cost,
        "correct_classifications": correct_count,
        "cost_per_correct_classification_usd": (
            round(total_cost / correct_count, 8)
            if total_cost is not None and correct_count
            else None
        ),
        "input_tokens": sum(call.get("input_tokens") or 0 for call in calls),
        "output_tokens": sum(call.get("output_tokens") or 0 for call in calls),
    }


def evaluate_operational_metrics(
    rows: list[dict[str, Any]],
    model_a: str,
    model_b: str,
    wall_clock_seconds: float,
    max_in_flight_calls: int,
    scored_metrics: dict[str, Any],
) -> dict[str, Any]:
    correct_a = scored_metrics["model_a"].get("correct_count", 0)
    correct_b = scored_metrics["model_b"].get("correct_count", 0)
    model_metrics = {
        "model_a": _model_metrics(rows, "model_a", model_a, correct_a, wall_clock_seconds),
        "model_b": _model_metrics(rows, "model_b", model_b, correct_b, wall_clock_seconds),
    }

    return {
        "max_in_flight_calls": max_in_flight_calls,
        "wall_clock_seconds": wall_clock_seconds,
        "models": model_metrics,
    }
