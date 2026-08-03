import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv


load_dotenv()

BASE_URL = "https://inference.do-ai.run/v1"


def _headers() -> dict[str, str]:
    model_access_key = os.environ.get("MODEL_ACCESS_KEY")
    if not model_access_key:
        raise RuntimeError("MODEL_ACCESS_KEY is not set")
    return {
        "Authorization": f"Bearer {model_access_key}",
        "Content-Type": "application/json",
    }


def get_models():
    r = requests.get(f"{BASE_URL}/models", headers=_headers())
    r.raise_for_status()
    return r.json()["data"]


def test_model(model_id):
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": "Reply with exactly one word."
            }
        ],
        "max_tokens": 1,
    }

    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=_headers(),
            json=payload,
            timeout=30,
        )

        if r.status_code == 200:
            return {
                "model": model_id,
                "status": "✅ Accessible",
                "http": 200,
                "message": "",
            }

        try:
            err = r.json()
            msg = err.get("message") or err.get("error", {}).get("message", "")
        except Exception:
            msg = r.text

        return {
            "model": model_id,
            "status": "❌ Forbidden" if r.status_code == 403 else "⚠️ Failed",
            "http": r.status_code,
            "message": msg,
        }

    except Exception as e:
        return {
            "model": model_id,
            "status": "❌ Error",
            "http": "",
            "message": str(e),
        }


def main():
    models = get_models()

    print(f"Found {len(models)} models\n")

    results = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(test_model, m["id"]): m["id"]
            for m in models
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            print(
                f"{result['status']:15} "
                f"{result['model']:35} "
                f"{result['http']} "
                f"{result['message']}"
            )

    results.sort(key=lambda x: x["model"])

    with open("data/available_models.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["model", "status", "http", "message"],
        )
        writer.writeheader()
        writer.writerows(results)

    print("\nSaved results to data/available_models.csv")


if __name__ == "__main__":
    main()