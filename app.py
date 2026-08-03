from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from models.available_models import AVAILABLE_MODELS
from services.comparison_service import run_model_comparison
from services.inference_service import ModelInferenceError


app = FastAPI(title="LLM Eval Harness UI")
app.mount("/web", StaticFiles(directory="web"), name="web")



class RunRequest(BaseModel):
	model_a: str
	model_b: str


@app.get("/")
def root():
	return FileResponse("web/index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/models")
def get_models():
	return {"models": AVAILABLE_MODELS}


@app.post("/api/run-comparison")
def run_comparison(payload: RunRequest):
	if payload.model_a not in AVAILABLE_MODELS or payload.model_b not in AVAILABLE_MODELS:
		raise HTTPException(status_code=422, detail="Select models from the available model list")
	if payload.model_a == payload.model_b:
		raise HTTPException(status_code=422, detail="Model A and Model B must be different")

	try:
		return run_model_comparison(payload.model_a, payload.model_b)
	except ModelInferenceError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=502, detail=f"Model inference failed: {exc}") from exc
