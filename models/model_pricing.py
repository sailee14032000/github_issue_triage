"""
Per-token pricing for DigitalOcean-hosted Serverless Inference models.

Source: https://docs.digitalocean.com/products/inference/details/pricing/
Last verified: 1 Jul 2026. Rates are USD per 1,000,000 tokens.
"""

MODEL_RATES_PER_MILLION = {
    "alibaba-qwen3-32b": (0.25, 0.55),
    "qwen3-coder-flash": (0.45, 1.70),
    "qwen3.5-397b-a17b": (0.385, 2.45),
    "deepseek-3.2": (0.425, 1.36),
    "deepseek-4-flash": (0.112, 0.224),
    "deepseek-v4-pro": (1.392, 2.784),
    "deepseek-r1-distill-llama-70b": (0.99, 0.99),
    "gemma-4-31B-it": (0.18, 0.50),
    "glm-5": (0.75, 2.40),
    "glm-5.1": (0.975, 4.30),
    "glm-5.2": (1.05, 4.40),
    "kimi-k2.5": (0.375, 2.025),
    "kimi-k2.6": (0.76, 3.20),
    "llama-4-maverick": (0.25, 0.87),
    "llama3.3-70b-instruct": (0.65, 0.65),
    "mimo-v2.5-pro": (0.60, 3.00),
    "minimax-m2.5": (0.225, 0.90),
    "mistral-3-14B": (0.20, 0.20),
    "nemotron-3-nano-omni": (0.50, 0.90),
    "nemotron-3-ultra-550b": (0.90, 1.70),
    "nemotron-nano-12b-v2-vl": (0.20, 0.60),
    "nvidia-nemotron-3-super-120b": (0.21, 0.455),
    "openai-gpt-oss-120b": (0.10, 0.70),
    "openai-gpt-oss-20b": (0.05, 0.45),
}


def calculate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in MODEL_RATES_PER_MILLION:
        raise KeyError(
            f"No pricing entry for model '{model}'. Verify it is live on DigitalOcean "
            "Serverless Inference and add its rate before running the evaluation."
        )

    input_rate, output_rate = MODEL_RATES_PER_MILLION[model]
    input_cost = (input_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * output_rate
    return round(input_cost + output_cost, 8)
