import os
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
from gradient import APITimeoutError, Gradient, RateLimitError

from models.category_enum import map_to_issue_category
from models.model_pricing import calculate_cost_usd


load_dotenv()


class ModelInferenceError(RuntimeError):
    pass


class InferenceCallError(ModelInferenceError):
    def __init__(self, message: str, latency_seconds: float, error_type: str):
        super().__init__(message)
        self.latency_seconds = latency_seconds
        self.error_type = error_type


def require_model_access_key() -> str:
    model_access_key = os.environ.get("MODEL_ACCESS_KEY")
    if not model_access_key:
        raise ModelInferenceError("MODEL_ACCESS_KEY is not set")
    return model_access_key


def _build_client() -> Gradient:
    return Gradient(model_access_key=require_model_access_key())


def run_model_inference(model_name: str, prompt: str, max_tokens: int = 120) -> dict[str, Any]:
    client = _build_client()
    started_at = perf_counter()
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        if isinstance(exc, RateLimitError):
            error_type = "rate_limit"
        elif isinstance(exc, (APITimeoutError, TimeoutError)):
            error_type = "timeout"
        else:
            error_type = "other"
        raise InferenceCallError(str(exc), perf_counter() - started_at, error_type) from exc

    if not response.choices:
        raise InferenceCallError(
            "No choices returned from inference API",
            perf_counter() - started_at,
            "other",
        )

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise InferenceCallError(
            "Empty response returned from inference API",
            perf_counter() - started_at,
            "other",
        )

    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else None
    output_tokens = usage.completion_tokens if usage else None
    cost_usd = (
        calculate_cost_usd(model_name, input_tokens, output_tokens)
        if input_tokens is not None and output_tokens is not None
        else None
    )
    mapped_category = map_to_issue_category(content)
    return {
        "model": model_name,
        "response": content,
        "category": mapped_category.value,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "latency_seconds": perf_counter() - started_at,
    }
